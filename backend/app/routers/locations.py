# routers/locations.py — Konum yönetimi CRUD endpoint'leri (liste destekli)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.location import Location
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/locations", tags=["Konum Yönetimi"])


class LocationCreate(BaseModel):
    list_name: str = "Genel"
    name: str
    city: str | None = None
    instagram_location_pk: str | None = None
    lat: str | None = None
    lng: str | None = None


class LocationUpdate(BaseModel):
    list_name: str | None = None
    name: str | None = None
    city: str | None = None
    instagram_location_pk: str | None = None
    lat: str | None = None
    lng: str | None = None
    is_active: bool | None = None


class BulkLocationImport(BaseModel):
    list_name: str = "Genel"
    locations_text: str  # Her satır: isim|şehir


@router.get("")
async def list_locations(
    city: str | None = None,
    list_name: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm konumları listeler (liste ve şehir filtrelemesi)."""
    query = db.query(Location)
    if city:
        query = query.filter(Location.city == city)
    if list_name:
        query = query.filter(Location.list_name == list_name)
    items = query.order_by(Location.list_name, Location.name).all()

    # Şehir listesi
    cities = list(set(l.city for l in db.query(Location).all() if l.city))
    cities.sort()

    # Liste adları
    all_lists = list(set(
        l.list_name for l in db.query(Location).all() if l.list_name
    ))
    all_lists.sort()

    return {
        "total": len(items),
        "cities": cities,
        "lists": all_lists,
        "items": [
            {
                "id": l.id,
                "list_name": l.list_name or "Genel",
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
        list_name=data.list_name or "Genel",
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
    """Toplu konum import — her satır: isim|şehir. Hepsi aynı listeye eklenir."""
    lines = [l.strip() for l in data.locations_text.strip().split("\n") if l.strip()]
    added = 0
    for line in lines:
        parts = line.split("|")
        name = parts[0].strip()
        city = parts[1].strip() if len(parts) > 1 else None
        loc = Location(
            list_name=data.list_name or "Genel",
            name=name,
            city=city,
        )
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


@router.delete("/list/{list_name}")
async def delete_list(
    list_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bir listedeki tüm konumları siler."""
    items = db.query(Location).filter(Location.list_name == list_name).all()
    if not items:
        raise HTTPException(status_code=404, detail="Liste bulunamadı")
    count = len(items)
    for item in items:
        db.delete(item)
    db.commit()
    return {"message": f"'{list_name}' listesi silindi ({count} konum)"}
