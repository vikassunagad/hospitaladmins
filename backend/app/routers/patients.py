from fastapi import APIRouter, Depends

from app.database import get_db
from app.dependencies import current_user
from app.schemas import DischargeIn, TreatmentIn, patient_dict
from app.services import patient_service, reservation_service

router = APIRouter(prefix="/api/patients", tags=["Patients"])


def _result(db, user, patient):
    return {"patient": patient_dict(patient), "capacity": reservation_service.capacity_summary(db, user.hospital_id)}


@router.get("")
def list_patients(status: str = None, user=Depends(current_user), db=Depends(get_db)):
    return {"items": [patient_dict(p) for p in patient_service.list_patients(db, user.hospital_id, status)]}


@router.get("/{patient_id}")
def get_patient(patient_id: str, user=Depends(current_user), db=Depends(get_db)):
    return patient_dict(patient_service.get_patient(db, user.hospital_id, patient_id))


@router.post("/{patient_id}/admit")
def admit(patient_id: str, user=Depends(current_user), db=Depends(get_db)):
    return _result(db, user, patient_service.admit(db, user.hospital_id, patient_id, user.username))


@router.post("/{patient_id}/treatment")
def treatment(patient_id: str, body: TreatmentIn, user=Depends(current_user), db=Depends(get_db)):
    p = patient_service.start_treatment(db, user.hospital_id, patient_id, user.username, body.treatment_status,
                                        body.notes)
    return _result(db, user, p)


@router.post("/{patient_id}/discharge")
def discharge(patient_id: str, body: DischargeIn = DischargeIn(), user=Depends(current_user), db=Depends(get_db)):
    return _result(db, user, patient_service.discharge(db, user.hospital_id, patient_id, user.username, body.notes))
