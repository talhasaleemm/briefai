"""
Custom Templates router.

Endpoints
---------
GET    /api/v1/templates    — list user templates
POST   /api/v1/templates    — create a custom template
PUT    /api/v1/templates/id — update a custom template
DELETE /api/v1/templates/id — delete a custom template
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.database import User, CustomTemplate
from app.models.schemas import CustomTemplateCreate, CustomTemplateUpdate, CustomTemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/", response_model=List[CustomTemplateOut])
def get_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all custom templates for the authenticated user."""
    return db.query(CustomTemplate).filter(CustomTemplate.user_id == current_user.id).all()


@router.post("/", response_model=CustomTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    req: CustomTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new custom template."""
    db_template = CustomTemplate(
        user_id=current_user.id,
        name=req.name,
        system_prompt=req.system_prompt,
        prompt_template=req.prompt_template,
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.put("/{template_id}", response_model=CustomTemplateOut)
def update_template(
    template_id: int,
    req: CustomTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing custom template."""
    db_template = db.query(CustomTemplate).filter(
        CustomTemplate.id == template_id,
        CustomTemplate.user_id == current_user.id
    ).first()
    
    if not db_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or unauthorized.",
        )
    
    if req.name is not None:
        db_template.name = req.name
    if req.system_prompt is not None:
        db_template.system_prompt = req.system_prompt
    if req.prompt_template is not None:
        db_template.prompt_template = req.prompt_template
        
    db.commit()
    db.refresh(db_template)
    return db_template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom template."""
    db_template = db.query(CustomTemplate).filter(
        CustomTemplate.id == template_id,
        CustomTemplate.user_id == current_user.id
    ).first()
    
    if not db_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or unauthorized.",
        )
        
    db.delete(db_template)
    db.commit()
    return None
