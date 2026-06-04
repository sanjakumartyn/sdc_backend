from typing import List, Optional, Tuple
from django.db.models import QuerySet
from features.signals.models import Signal
from common.exception.base_exception import NotFoundException

class SignalRepository:
    """
    Data Access Layer (Repository) encapsulating all direct database interactions 
    for the Signal model using Django ORM.
    """
    
    @staticmethod
    def get_by_id(signal_id: str) -> Signal:
        """Retrieves a single Signal by ID, raising a NotFoundException if missing."""
        try:
            return Signal.objects.get(pk=signal_id)
        except Signal.DoesNotExist:
            raise NotFoundException(f"Signal with ID {signal_id} not found")

    @staticmethod
    def list_all(
        status: Optional[str] = None, 
        source: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Signal], int]:
        """
        Retrieves a paginated list of Signals alongside the total record count.
        """
        queryset = Signal.objects.all()
        
        if status:
            queryset = queryset.filter(status=status)
        if source:
            queryset = queryset.filter(source__iexact=source)
            
        total = queryset.count()
        results = list(queryset[offset:offset + limit])
        
        return results, total

    @staticmethod
    def create(data: dict) -> Signal:
        """Saves a new Signal record in the database."""
        return Signal.objects.create(**data)

    @staticmethod
    def update(signal: Signal, update_data: dict) -> Signal:
        """Updates and persists modified attributes on an existing Signal instance."""
        for field, value in update_data.items():
            if value is not None:
                setattr(signal, field, value)
        signal.save()
        return signal

    @staticmethod
    def delete(signal: Signal) -> None:
        """Removes a Signal record permanently from the database."""
        signal.delete()
