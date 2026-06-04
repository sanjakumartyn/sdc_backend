from ninja import Router

from common.response.base_response import APIEnvelope
from common.response.response_builder import ResponseBuilder
from features.callAgents.schema import QuestionRequestSchema, QuestionResponseSchema
from features.callAgents.service import CallAgentsService

router = Router()


@router.post("/question", response={200: APIEnvelope[QuestionResponseSchema]})
def question(request, payload: QuestionRequestSchema):
	result = CallAgentsService.question(payload.model_dump())
	return ResponseBuilder.success(result)

