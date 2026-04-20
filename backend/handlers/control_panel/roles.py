from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.user_service import create_user_role_association, get_user_role_association_by_code, delete_role_association
from utils.responce_helps import response_success, response_error
from models.users_model import UserRole

router = APIRouter(prefix='/control-panel/roles', tags=['Roles'])

@router.get('/')
async def get_roles(response: Response, db_session: AsyncSession = Depends(get_db_session)):
    roles_list = [role.value for role in UserRole]
    return response_success(roles=roles_list)

@router.post('/', dependencies=[Depends(auth_middle)])
async def create_role(request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    input_data = await request.json()

    if not input_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message='Нет входных параметров', code="no_data")

    allowed_fields = ['role', 'user_id']
    updated_data = {k: v for k, v in input_data.items() if k in allowed_fields}

    if not updated_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message='Нет обязательных полей', code="invalid_data")
    
    if await get_user_role_association_by_code(
        session=db_session,
        user_id=updated_data['user_id'],
        role_code=updated_data['role']
    ) is not None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message='Роль уже существует', code="invalid_data")

    if await create_user_role_association(
        session=db_session, 
        user_id=updated_data['user_id'], 
        role_code=updated_data['role'], 
        assigned_by=request.state.user['sub']
    ) == False:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message='Ошибка создания роли', code="invalid_data")
    
    return response_success(message='Роль успешно добавлена', code="role_created")

@router.delete('/{user_id}/{role_code}', dependencies=[Depends(auth_middle)])
async def remove_role(user_id: str, role_code: str, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    if not user_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message='Нет входных параметров', code="no_data")

    if role_code == 'user':
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message='Нельзя удалить роль пользователя', code="invalid_data")
    
    target_role = await get_user_role_association_by_code(
        session=db_session,
        user_id=user_id,
        role_code=role_code
    )

    if target_role is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message="Роль которую вы хотите удалить не существует", code='NOT_FOUND')

    if await delete_role_association(
        session=db_session,
        target_role=target_role
    ) == False:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message="Ошибка удаления роли", code='NOT_FOUND')
    
    return response_success(message="Роль успешно удалена", code='role_deleted')