from typing import List, Optional, Tuple
from django.db.models import QuerySet
from features.deals.models import Deal
from common.exception.base_exception import NotFoundException

class DealRepository:
    """
    Data Access Layer (Repository) encapsulating all direct database interactions 
    for the Deal model using Django ORM.
    """
    
    @staticmethod
    def get_by_id(deal_id: str) -> Deal:
        """Retrieves a single Deal by ID, raising a NotFoundException if missing."""
        try:
            return Deal.objects.get(pk=deal_id)
        except Deal.DoesNotExist:
            raise NotFoundException(f"Deal with ID {deal_id} not found")

    @staticmethod
    def list_all(
        stage: Optional[str] = None, 
        min_value: Optional[float] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Deal], int]:
        """
        Retrieves a paginated list of Deals alongside the total record count.
        """
        queryset = Deal.objects.all()
        
        if stage:
            queryset = queryset.filter(stage=stage)
        if min_value is not None:
            queryset = queryset.filter(value__gte=min_value)
            
        total = queryset.count()
        results = list(queryset[offset:offset + limit])
        
        return results, total

    @staticmethod
    def create(data: dict) -> Deal:
        """Saves a new Deal record in the database."""
        return Deal.objects.create(**data)

    @staticmethod
    def update(deal: Deal, update_data: dict) -> Deal:
        """Updates and persists modified attributes on an existing Deal instance."""
        for field, value in update_data.items():
            if value is not None:
                setattr(deal, field, value)
        deal.save()
        return deal

    @staticmethod
    def delete(deal: Deal) -> None:
        """Removes a Deal record permanently from the database."""
        deal.delete()
