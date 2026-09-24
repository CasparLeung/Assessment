from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import uuid
from database import Assessment, get_db

# Initialize the FastAPI
app = FastAPI()

"""
Error responses
"""
# 1.Category 4xx: Route Not Found (404), Method Not Allowed (405), etc.
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status_code": exc.status_code,
            "error": "Client Error",
            "detail": exc.detail,
        },
    )


# 2.Category 4xx: Validation & Missing Parameters (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    formatted_errors = []
    for err in exc.errors():
        field_name = err["loc"][-1]
        formatted_errors.append(f"Field '{field_name}': {err['msg']}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "error": "Unprocessable Entity",
            "detail": formatted_errors,
        },
    )


# 3.Category 5xx: Database Crashes & Connection Drops (500)
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database failure on %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "error": "Internal Database Error",
            "detail": "An unexpected database error occurred. Please try again later.",
        },
    )


# 4. Category 5xx: Catch-All Global Fallback (Uncaught Server Exceptions)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.critical("Unhandled Server Crash on %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "error": "Internal Server Error",
            "detail": "An unexpected application error occurred.",
        },
    )

# Define the incoming request schema 
class IdentifierPayload(BaseModel):
    id1: str = Field(..., min_length=1, description="First unique identifier") # avoid empty strings
    id2: str = Field(..., min_length=1, description="Second unique identifier")

# Define the response schema
class UserResponse(BaseModel):
    userID: str

# API POST endpoint
@app.post(
    "/process-identifiers",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,  # Returns 200 OK on success
    summary="Accept and process two identifiers",
)
def handle_identifiers(payload: IdentifierPayload, db: Session = Depends(get_db)):
    # Validates incoming JSON against IdentifierPayload.
    
    # Reject inputs that contain only empty whitespace
    clean_id1 = payload.id1.strip()
    clean_id2 = payload.id2.strip()
    
    # If id1 or id2 is missing, wrong type, or empty, returns 422 immediately.
    if not clean_id1 or not clean_id2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fields 'id1' and 'id2' must not be blank whitespace.",
        )

    try:
        # Check if record already exists
        existing_record = (
            db.query(Assessment)
            .filter(Assessment.id1 == clean_id1, Assessment.id2 == clean_id2)
            .first()
        )

        if existing_record:
            return {"userID": existing_record.userID}

        # If not found, generate new UUID v4
        new_user_id = str(uuid.uuid4())
        new_record = Assessment(
            userID=new_user_id,
            id1=clean_id1,
            id2=clean_id2,
        )

        # Store in MySQL with race-condition safety
        try: # Store new userID in database and return generated userID in JSON format
            db.add(new_record)
            db.commit()
            db.refresh(new_record)
            return {"userID": new_record.userID}
        except IntegrityError:
            # Fallback if simultaneously request 
            db.rollback()
            existing_record = (
                db.query(Assessment)
                .filter(Assessment.id1 == clean_id1, Assessment.id2 == clean_id2)
                .first()
            )
            if existing_record:
                return {"userID": existing_record.userID}
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A conflict occurred while creating the record. Please retry.",
            )

    except SQLAlchemyError as exc:
        db.rollback()
        # Log technical error internally; return clean generic error to user
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected database error occurred.",
        )
    
if __name__ == "__main__":
    from fastapi.testclient import TestClient

    # Create an in-memory client for the FastAPI app
    client = TestClient(app)

    payload = {
        "id1": "ABC123",
        "id2": "XYZ456"
    }

    print("--- 1. First Request ---")
    response_1 = client.post("/process-identifiers", json=payload)
    print("Status:", response_1.status_code)
    print("Response:", response_1.json())

    print("\n--- 2. Second Request (Identical Payload) ---")
    response_2 = client.post("/process-identifiers", json=payload)
    print("Status:", response_2.status_code)
    print("Response:", response_2.json())

    # Verify both calls returned the identical UUID
    assert response_1.json()["userID"] == response_2.json()["userID"]
    print("\nSUCCESS: Both calls returned the same userID.")