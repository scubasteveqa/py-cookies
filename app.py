# This code is to demonstrate an issue where setting a value in Starlette middleware and passing to shiny session, the value is lost on browser refresh.
# Steps to reproduce.
# 1. Verify the environment_prefix below is "prod" before deploying.
# 2. Deploy using  rsconnect deploy shiny -n <name> --entrypoint app_example:app --title <app_title>  #app_title is defined below
# 3. Restart the shiny app using the shinyapps.io UI. <- *** IMPORTANT*** as the issue is not present if app is not restarted.
# 4. Click the dummy button in UI and refresh the browser. 
# 5. The value displayed should be "this_is_dummy_value". 
# 6. The value should remain "this_is_dummy_value" after browser refreshed. However, often it is None once the browser is refreshed. Note that in local testing there is no issue.
# 7. Press the reset value button to clear the value and repeat.

import os
import uvicorn
from shiny import App, reactive, render, ui
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Route, Mount
from starlette.middleware.sessions import SessionMiddleware

environment_prefix = "prod"  #### <--- change to prod when deploying to shinyapps.io. change to test when testing locally.  ####
app_title = "example"
redirect_url_append = "/" + app_title.lower() if environment_prefix == "prod" else "" 

### --- Server ---
def server(input, output, session):
    session_id = session.id
    cookies = session.http_conn.cookies
    print("Cookies:", cookies)
    print("session_id: ", session_id)
    print("value should be 'this_is_dummy_value' after page reload: ", session.http_conn.session.get("value"))
               
    # Clicking dummy_btn passes a value called "this_is_dummy_value" which should be retained across browser refreshes
    @reactive.effect
    @reactive.event(input.dummy_btn)
    async def pass_value():
        # pass value
        url = f"/dummy?value=this_is_dummy_value"
        await session.send_custom_message("redirect", redirect_url_append + url)

    # Clicking reset_btn clears the value
    @reactive.effect
    @reactive.event(input.reset_btn)
    async def reset_value():
        # clear value
        url = f"/dummy?value="
        await session.send_custom_message("redirect", redirect_url_append + url)
        
    # --- UI output ---
    @output
    @render.ui
    def main_app():
        current_value = session.http_conn.session.get("value")
        return ui.div(
            ui.h3("Welcome to Shiny-Starlette Hybrid App"),
            ui.input_action_button("dummy_btn", "dummy"),
            ui.h2("After user clicks dummy button above, value should be 'this_is_dummy_value' even after browser refresh: value = ", current_value),
            ui.input_action_button("reset_btn", "reset value"),
        )


async def dummy_route(request: Request):
    # Setting the passed user info value 
    request.session["value"] = request.query_params.get("value")

    print("this_value", request.session["value"])
    return RedirectResponse(url=redirect_url_append + "/")

    
auth_routes = [
    Route("/dummy", dummy_route, methods=["GET"])    
]

# Create the Shiny app
app_ui = ui.page_fluid(
    ui.output_ui("main_app"),

    # Custom JS for redirect
    ui.tags.script("""
        Shiny.addCustomMessageHandler("redirect", function(url) {
            console.log("Redirecting to:", url);
            window.location.href = url;
        });
    """)
)

shiny_app = App(app_ui, server)

# --- Build Starlette app ---
app = Starlette(debug=True, routes=[
        *auth_routes,
])

app.add_middleware(SessionMiddleware,
                   secret_key = "SUPERSECRET!!!", 
                   max_age = 3600*12, # session cookie for 12 hrs 
                   same_site = "none" if environment_prefix=="prod" else "lax", 
                   https_only = True if environment_prefix=="prod" else False
                  )  

# Mount the Shiny app
app.routes.append(Mount("/", app=shiny_app))  

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
    
