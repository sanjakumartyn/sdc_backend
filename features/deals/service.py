from typing import List, Optional, Tuple, Dict, Any
from config.constants import DEAL_STAGES, DEAL_STAGE_CLOSED_WON, DEAL_STAGE_CLOSED_LOST
from common.utils.helpers import clean_input_string
from common.exception.base_exception import BadRequestException
from features.deals.models import Deal
from features.deals.repository import DealRepository

class DealService:
    """
    Business Logic Layer (Service) coordinating validations, 
    data cleaning, and repository mutations for the Deals domain.
    """
    
    @staticmethod
    def get_deal(deal_id: str) -> Deal:
        """Retrieves a specific deal or propagates the Not Found error."""
        return DealRepository.get_by_id(deal_id)

    @staticmethod
    def list_deals(
        stage: Optional[str] = None,
        min_value: Optional[float] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Deal], int]:
        """Orchestrates query lists and pagination bounds."""
        return DealRepository.list_all(stage=stage, min_value=min_value, limit=limit, offset=offset)

    @staticmethod
    def create_deal(data: Dict[str, Any]) -> Deal:
        """
        Validates business rules before committing the new deal.
        Automatically updates win probability based on pipeline stage.
        """
        data["name"] = clean_input_string(data.get("name"))
        if not data["name"]:
            raise BadRequestException("Deal name cannot be empty or solely white-spaces.")

        # Business Rule: Validate stage choice
        stage = data.get("stage", "PROSPECTING")
        valid_stages = [choice[0] for choice in DEAL_STAGES]
        if stage not in valid_stages:
            raise BadRequestException(f"Invalid deal stage: '{stage}'")

        # Business Rule: Automatically adjust probability if standard stage transitions occur
        if stage == DEAL_STAGE_CLOSED_WON:
            data["probability"] = 100
        elif stage == DEAL_STAGE_CLOSED_LOST:
            data["probability"] = 0
            
        return DealRepository.create(data)

    @staticmethod
    def update_deal(deal_id: str, update_data: Dict[str, Any]) -> Deal:
        """
        Applies business checks (like valid stage updates and probability transitions) 
        before modifying properties.
        """
        deal = DealRepository.get_by_id(deal_id)
        
        # Clean update name if present
        if "name" in update_data and update_data["name"] is not None:
            update_data["name"] = clean_input_string(update_data["name"])
            if not update_data["name"]:
                raise BadRequestException("Deal name cannot be empty.")
                
        # Validate stage if updating
        new_stage = update_data.get("stage")
        if new_stage:
            valid_stages = [choice[0] for choice in DEAL_STAGES]
            if new_stage not in valid_stages:
                raise BadRequestException(
                    message=f"Invalid deal stage '{new_stage}' provided.",
                    details={"allowed_stages": valid_stages}
                )
                
            # Business Rule: Automatically adjust probability if closed stage is set
            if new_stage == DEAL_STAGE_CLOSED_WON:
                update_data["probability"] = 100
            elif new_stage == DEAL_STAGE_CLOSED_LOST:
                update_data["probability"] = 0

        return DealRepository.update(deal, update_data)

    @staticmethod
    def delete_deal(deal_id: str) -> None:
        """Deletes a deal by locating it first."""
        deal = DealRepository.get_by_id(deal_id)
        DealRepository.delete(deal)
