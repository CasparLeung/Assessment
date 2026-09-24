from fastapi import FastAPI, status
from pydantic import BaseModel, Field

# Initialize the FastAPI
app = FastAPI()


# Define the incoming request schema using Pydantic
class IdentifierPayload(BaseModel):
    id1: str = Field(..., min_length=1, description="First unique identifier") # avoid empty strings
    id2: str = Field(..., min_length=1, description="Second unique identifier")


# Define the POST route
@app.post(
    "/process-identifiers",
    status_code=status.HTTP_200_OK,  # Returns 200 OK on success
    summary="Accept and process two identifiers",
)
def handle_identifiers(payload: IdentifierPayload):
    # FastAPI automatically validates incoming JSON against IdentifierPayload.
    
    # Reject inputs that contain only empty whitespace
    clean_id1 = payload.id1.strip()
    clean_id2 = payload.id2.strip()
    
    # If id1 or id2 is missing, wrong type, or empty, returns 422 immediately.
    if not clean_id1 or not clean_id2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fields 'id1' and 'id2' must not be blank whitespace.",
        )

    # backend logic / database lookups
    print(f"Received id1: {clean_id1}, id2: {clean_id2}")

    # Return the response payload
    return {
        "status": "success",
        "data": {
            "id1": clean_id1,
            "id2": clean_id2,
        },
    }