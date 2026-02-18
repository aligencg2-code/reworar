# routers/locations.py — Konum yönetimi CRUD endpoint'leri
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.location import Location
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/locations", tags=["Konum Yönetimi"])


class LocationCreate(BaseModel):
    name: str
    city: str | None = None
    instagram_location_pk: str | None = None
    lat: str | None = None
    lng: str | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    instagram_location_pk: str | None = None
    lat: str | None = None
    lng: str | None = None
    is_active: bool | None = None


class BulkLocationImport(BaseModel):
    locations_text: str  # Her satır: isim|şehir


@router.get("")
async def list_locations(
    city: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm konumları listeler."""
    query = db.query(Location)
    if city:
        query = query.filter(Location.city == city)
    items = query.order_by(Location.city, Location.name).all()

    # Şehir listesi
    cities = list(set(l.city for l in db.query(Location).all() if l.city))
    cities.sort()

    return {
        "total": len(items),
        "cities": cities,
        "items": [
            {
                "id": l.id,
                "name": l.name,
                "city": l.city,
                "instagram_location_pk": l.instagram_location_pk,
                "lat": l.lat,
                "lng": l.lng,
                "is_active": l.is_active,
                "created_at": l.created_at.isoformat(),
            }
            for l in items
        ],
    }


@router.post("")
async def create_location(
    data: LocationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yeni konum ekler."""
    loc = Location(
        name=data.name,
        city=data.city,
        instagram_location_pk=data.instagram_location_pk,
        lat=data.lat,
        lng=data.lng,
    )
    db.add(loc)
    db.commit()
    return {"message": "Konum eklendi", "id": loc.id}


@router.post("/bulk-import")
async def bulk_import_locations(
    data: BulkLocationImport,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toplu konum import — her satır: isim|şehir."""
    lines = [l.strip() for l in data.locations_text.strip().split("\n") if l.strip()]
    added = 0
    for line in lines:
        parts = line.split("|")
        name = parts[0].strip()
        city = parts[1].strip() if len(parts) > 1 else None
        loc = Location(name=name, city=city)
        db.add(loc)
        added += 1
    db.commit()
    return {"message": f"{added} konum eklendi", "added": added}


@router.put("/{location_id}")
async def update_location(
    location_id: int,
    data: LocationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Konum günceller."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Konum bulunamadı")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(loc, key, value)
    db.commit()
    return {"message": "Konum güncellendi"}


@router.delete("/{location_id}")
async def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Konum siler."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Konum bulunamadı")
    db.delete(loc)
    db.commit()
    return {"message": "Konum silindi"}
