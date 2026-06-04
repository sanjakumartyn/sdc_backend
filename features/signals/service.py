from typing import List, Optional, Tuple, Dict, Any
from config.constants import SIGNAL_STATUSES
from common.utils.helpers import clean_input_string
from common.exception.base_exception import BadRequestException
from features.signals.models import Signal
from features.signals.repository import SignalRepository

class SignalService:
    """
    Business Logic Layer (Service) coordinating validations, 
    data cleaning, and repository mutations for the Signals domain.
    """
    
    @staticmethod
    def get_signal(signal_id: str) -> Signal:
        """Retrieves a specific signal or propagates the Not Found error."""
        return SignalRepository.get_by_id(signal_id)

    @staticmethod
    def list_signals(
        status: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Signal], int]:
        """Orchestrates query lists and pagination bounds."""
        return SignalRepository.list_all(status=status, source=source, limit=limit, offset=offset)

    @staticmethod
    def create_signal(data: Dict[str, Any]) -> Signal:
        """
        Validates business rules (e.g., sanitizing text input) 
        before committing the new signal.
        """
        # Sanitize text fields
        data["title"] = clean_input_string(data.get("title"))
        data["source"] = clean_input_string(data.get("source")).upper()
        
        if not data["title"]:
            raise BadRequestException("Signal title cannot be empty or solely white-spaces.")
            
        return SignalRepository.create(data)

    @staticmethod
    def update_signal(signal_id: str, update_data: Dict[str, Any]) -> Signal:
        """
        Applies business checks (like valid status updates) 
        before modifying properties.
        """
        signal = SignalRepository.get_by_id(signal_id)
        
        # Verify status choices if status is provided in update
        new_status = update_data.get("status")
        if new_status:
            valid_statuses = [choice[0] for choice in SIGNAL_STATUSES]
            if new_status not in valid_statuses:
                raise BadRequestException(
                    message=f"Invalid status '{new_status}' provided.",
                    details={"allowed_statuses": valid_statuses}
                )
                
        # Clean update titles/sources if present
        if "title" in update_data and update_data["title"] is not None:
            update_data["title"] = clean_input_string(update_data["title"])
        if "source" in update_data and update_data["source"] is not None:
            update_data["source"] = clean_input_string(update_data["source"]).upper()

        return SignalRepository.update(signal, update_data)

    @staticmethod
    def delete_signal(signal_id: str) -> None:
        """Deletes a signal by locating it first."""
        signal = SignalRepository.get_by_id(signal_id)
        SignalRepository.delete(signal)
