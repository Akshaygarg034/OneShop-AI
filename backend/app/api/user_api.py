
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Request, Response, Depends

from app.controllers.user_controller import register_user
from app.controllers.user_controller import login_user
from app.controllers.user_controller import logout_user
from app.controllers.user_controller import change_password
from app.controllers.user_controller import get_current_user
from app.controllers.user_controller import update_account_details

from app.middlewares.auth_middlewares import verify_jwt

router = APIRouter()


@router.post("/register")
async def register_route(
    request: Request,
    avatar: UploadFile = File(...),
    cover_image: Optional[UploadFile] = File(None, alias="coverImage"),
):
    """
    Registers a user with an avatar and optional cover image.
    """
    return await register_user(request, avatar)


@router.post("/login")
async def login_route(request: Request, response: Response):
    """
    Authenticates a user and logs them into the system.
    """
    return await login_user(request, response)


# @router.post("/auth/google")
# async def login_with_google_route(request: Request, response: Response):
#     """
#     Authenticates a user with Google validation and logs them into the system.
#     """
#     print(f"Request: {request}, Response: {response}")
#     return await login_with_google(request, response)



@router.post("/change-password",dependencies=[Depends(verify_jwt)])
async def change_password_route(request: Request):
    """
    Changes the user password (JWT required).
    """
    return await change_password(request)


@router.get("/current-user", dependencies=[Depends(verify_jwt)])
async def get_current_user_route(request: Request):
    """
    Gets the current authenticated user.
    """
    return await get_current_user(request) 


@router.patch("/update-account", dependencies=[Depends(verify_jwt)])
async def update_account_details_route(request: Request):
    """
    Updates user account details.
    """
    return await update_account_details(request)
