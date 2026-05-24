from pydantic import BaseModel, Field, field_validator

class ClipGenerateRequest(BaseModel):
    song_id: int = Field(..., alias="songId", description="ID of the song to slice")
    start_time: float = Field(..., alias="startTime", ge=0, description="Start time of the clip in seconds")
    end_time: float = Field(..., alias="endTime", description="End time of the clip in seconds")

    @field_validator("end_time")
    @classmethod
    def validate_clip_duration(cls, end_time: float, info) -> float:
        start_time = info.data.get("start_time")
        if start_time is not None:
            if end_time <= start_time:
                raise ValueError("End time must be greater than start time")
            duration = end_time - start_time
            if duration > 30.0:
                raise ValueError("Clip duration cannot exceed 30 seconds")
        return end_time

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "songId": 1,
                "startTime": 75.0,
                "endTime": 105.0
            }
        }
    }
