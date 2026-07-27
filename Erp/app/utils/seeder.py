"""Demo data seeder.

Runs once on first boot (when the ``users`` table is empty). All history is
generated **relative to today**, so the dashboards are always alive no matter
when the app is started. ``random.seed(42)`` keeps runs reproducible.
"""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (CONSULTATION_FEES, OT_BASE_CHARGES,
                                PHYSIO_SESSION_CHARGE, ROOM_RATES)
from app.core.security import hash_password
from app.models import (Admission, Appointment, Attendance, Bill, BillItem,
                        CareLog, Consultation, Medicine, Mediclaim,
                        OperationTheatre, Patient, PatientDocument,
                        PhysioPlan, PhysioSession, Prescription,
                        PrescriptionItem, Reminder, Room, SalaryPayment,
                        Staff, StockTransaction, Surgery, User)
from app.models.enums import (AdmissionStatus, AdmissionType,
                              AppointmentStatus, AttendanceStatus,
                              BillItemCategory, BillStatus, BillType,
                              BookedVia, CareLogType, ClaimStatus, Department,
                              Designation, DocumentType, OTCategory, OTStatus,
                              PayrollMode, PhysioExercise, PhysioModality,
                              PhysioTraction, ReminderCategory, Role,
                              RoomStatus, RoomType, Sex, StockTxnType,
                              SurgeryStatus)
from app.services.ward_service import WardService
from app.utils.catalog import flat_service_names
from app.utils.ids import (appointment_code, bill_number, claim_number,
                           patient_code, payment_reference, txn_reference)

rng = random.Random(42)

PW_ADMIN = hash_password("Palaskar@2014")
PW_STAFF = hash_password("Staff@1234")
PW_PATIENT = hash_password("Patient@1234")


def _dt(days_ago: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(date.today() - timedelta(days=days_ago),
                            time(hour, minute))


async def seed_if_empty(db: AsyncSession) -> bool:
    count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    if count:
        return False
    await _seed(db)
    return True


async def _seed(db: AsyncSession) -> None:  # noqa: C901 — a seeder is a story
    today = date.today()

    # ------------------------------------------------------------- users/staff
    def staff_row(username, pw, role, name, sex, dob, desig, qual, dept, phone,
                  salary, joined, shift=("09:00", "17:00"), aadhar=None,
                  pan=None, acct=None, ifsc="HDFC0001234", bank="HDFC Bank, Vasai (W)"):
        user = User(username=username, hashed_password=pw, role=role,
                    full_name=name)
        db.add(user)
        return user, dict(full_name=name, sex=sex, date_of_birth=dob,
                          designation=desig, qualification=qual,
                          department=dept, phone=phone,
                          email=f"{username}@palaskarhospital.in",
                          address="Vasai (W), Palghar 401202",
                          monthly_salary=salary, date_joined=joined,
                          shift_start=shift[0], shift_end=shift[1],
                          aadhar_number=aadhar, pan_number=pan,
                          bank_account_number=acct, bank_ifsc=ifsc,
                          bank_name=bank)

    rows = [
        staff_row("sameer", PW_ADMIN, Role.SUPER_ADMIN,
                  "Dr. Sameer S. Palaskar", Sex.MALE, date(1978, 4, 12),
                  Designation.DOCTOR,
                  "D.N.B (ORTHO), D.Ortho, M.N.A.M.S (Ortho)", "ORTHOPAEDICS",
                  "9545081608", 250000, date(2014, 3, 1), ("11:00", "21:00"),
                  "234567890123", "ABCPP1234D", "50100234567891"),
        staff_row("lalan", PW_ADMIN, Role.SUPER_ADMIN,
                  "Dr. Lalan S. Palaskar", Sex.FEMALE, date(1980, 9, 25),
                  Designation.DOCTOR, "M.B.B.S, D.O.M.S", "OPHTHALMOLOGY",
                  "8087381866", 220000, date(2014, 3, 1), ("11:00", "18:00"),
                  "345678901234", "ABDPP5678E", "50100234567892"),
        staff_row("anita", PW_STAFF, Role.STAFF, "Anita R. Chaudhari",
                  Sex.FEMALE, date(1992, 6, 3), Designation.NURSE,
                  "G.N.M Nursing", "NURSING", "9822011223", 28000,
                  date(2017, 7, 10), ("08:00", "16:00"),
                  "456789012345", "AKJPC1122F", "50100234567893"),
        staff_row("kavita", PW_STAFF, Role.STAFF, "Kavita M. Patil",
                  Sex.FEMALE, date(1995, 11, 18), Designation.NURSE,
                  "B.Sc Nursing", "NURSING", "9822044556", 30000,
                  date(2019, 2, 4), ("14:00", "22:00"),
                  "567890123456", "AMHPP3344G", "50100234567894"),
        staff_row("priya", PW_STAFF, Role.STAFF, "Priya D. Shah", Sex.FEMALE,
                  date(1997, 1, 30), Designation.CLERK, "B.Com",
                  "FRONT OFFICE", "9822077889", 22000, date(2021, 6, 21),
                  ("09:00", "18:00"), "678901234567", "BNZPS5566H",
                  "50100234567895"),
        staff_row("suresh", PW_STAFF, Role.STAFF, "Suresh K. Gupta", Sex.MALE,
                  date(1988, 8, 14), Designation.PHARMACIST, "D.Pharm",
                  "PHARMACY", "9822099001", 32000, date(2016, 10, 3),
                  ("10:00", "20:00"), "789012345678", "CPQPG7788J",
                  "50100234567896"),
        staff_row("rohan", PW_STAFF, Role.STAFF, "Rohan V. Thakur", Sex.MALE,
                  date(1999, 3, 22), Designation.PHYSIOTHERAPIST, "B.P.Th",
                  "PHYSIOTHERAPY", "9822033445", 26000, date(2022, 8, 16),
                  ("08:00", "20:00"), "890123456789", "DRSPT9900K",
                  "50100234567897"),
        staff_row("meena", PW_STAFF, Role.STAFF, "Meena J. Vartak", Sex.FEMALE,
                  date(2001, 12, 5), Designation.INTERN, "G.N.M (Intern)",
                  "NURSING", "9822055667", 15000, date(2025, 1, 6),
                  ("08:00", "16:00"), "901234567890", "EFTPV2233L",
                  "50100234567898"),
    ]
    await db.flush()
    staff_objs: dict[str, Staff] = {}
    for user, kwargs in rows:
        s = Staff(user_id=user.id, **kwargs)
        db.add(s)
        staff_objs[user.username] = s
    await db.flush()
    sameer, lalan = staff_objs["sameer"], staff_objs["lalan"]
    anita, kavita = staff_objs["anita"], staff_objs["kavita"]
    rohan_pt = staff_objs["rohan"]

    # ---------------------------------------------------------------- patients
    patient_data = [
        ("Ramesh B. Sawant", Sex.MALE, date(1965, 5, 2), "B+", "9890011001",
         "ramesh", "Knee osteoarthritis since 2019"),
        ("Sunita R. Mhatre", Sex.FEMALE, date(1972, 8, 19), "O+", "9890011002",
         "sunita", "Cataract (left eye) operated 2023"),
        ("Vijay K. Raut", Sex.MALE, date(1988, 1, 25), "A+", "9890011003",
         "vijay", None),
        ("Alka P. Naik", Sex.FEMALE, date(1990, 3, 14), "AB+", "9890011004",
         None, "Cervical spondylosis"),
        ("Ganesh D. Patil", Sex.MALE, date(1955, 11, 8), "B-", "9890011005",
         None, "Diabetic · hypertensive"),
        ("Farida S. Shaikh", Sex.FEMALE, date(1983, 7, 27), "O-", "9890011006",
         None, None),
        ("Nitin G. Kadam", Sex.MALE, date(1996, 9, 9), "A-", "9890011007",
         None, "Sports injuries — footballer"),
        ("Shobha V. Churi", Sex.FEMALE, date(1948, 2, 17), "B+", "9890011008",
         None, "Glaucoma under observation"),
        ("Dinesh M. Bhoir", Sex.MALE, date(1979, 12, 1), "O+", "9890011009",
         None, None),
        ("Prachi A. Vaity", Sex.FEMALE, date(2003, 6, 21), "A+", "9890011010",
         None, None),
    ]
    patients: list[Patient] = []
    for i, (name, sex, dob, bg, phone, uname, hist) in enumerate(patient_data, 1):
        uid = None
        if uname:
            pu = User(username=uname, hashed_password=PW_PATIENT,
                      role=Role.PATIENT, full_name=name)
            db.add(pu)
            await db.flush()
            uid = pu.id
        p = Patient(patient_code=patient_code(i), user_id=uid, full_name=name,
                    sex=sex, date_of_birth=dob, blood_group=bg, phone=phone,
                    email=f"{uname}@gmail.com" if uname else None,
                    address="Vasai (W), Dist. Palghar 401202",
                    emergency_contact_name="Family", 
                    emergency_contact_phone="9890000000",
                    allergies="None known" if i % 3 else "Penicillin",
                    medical_history=hist, created_by_user_id=1,
                    created_at=_dt(rng.randint(30, 400), 11))
        db.add(p)
        patients.append(p)
    await db.flush()

    # --------------------------------------------------------------- medicines
    med_rows = [
        ("Tab Diclofenac 50 mg", "Diclofenac sodium", "Analgesic", "strip of 10", 35, 120, 30),
        ("Tab Paracetamol 650 mg", "Paracetamol", "Antipyretic", "strip of 10", 25, 200, 50),
        ("Tab Aceclofenac-SR 200 mg", "Aceclofenac", "Analgesic", "strip of 10", 60, 90, 25),
        ("Cap Pregabalin 75 mg", "Pregabalin", "Neuropathic", "strip of 10", 110, 60, 20),
        ("Tab Etoricoxib 90 mg", "Etoricoxib", "Analgesic", "strip of 10", 95, 80, 20),
        ("Tab Calcium + D3", "Calcium carbonate", "Supplement", "strip of 15", 55, 150, 40),
        ("Cap Omeprazole 20 mg", "Omeprazole", "Antacid", "strip of 15", 40, 140, 40),
        ("Inj Diclofenac 75 mg/3 ml", "Diclofenac", "Injection", "ampoule", 18, 75, 25),
        ("Inj Ceftriaxone 1 g", "Ceftriaxone", "Antibiotic", "vial", 65, 50, 20),
        ("Inj Tramadol 50 mg", "Tramadol", "Analgesic", "ampoule", 22, 40, 15),
        ("Tab Amoxiclav 625 mg", "Amoxicillin+Clavulanate", "Antibiotic", "strip of 10", 180, 70, 20),
        ("Eye drop Moxifloxacin 0.5%", "Moxifloxacin", "Ophthalmic", "5 ml bottle", 145, 60, 15),
        ("Eye drop Carboxymethylcellulose", "CMC 0.5%", "Ophthalmic", "10 ml bottle", 120, 85, 20),
        ("Eye drop Timolol 0.5%", "Timolol", "Ophthalmic", "5 ml bottle", 90, 45, 12),
        ("Eye drop Prednisolone 1%", "Prednisolone acetate", "Ophthalmic", "5 ml bottle", 110, 40, 12),
        ("Eye ointment Tobramycin", "Tobramycin", "Ophthalmic", "5 g tube", 75, 35, 10),
        ("Tab Vitamin B-complex", "B-complex", "Supplement", "strip of 10", 30, 160, 40),
        ("Tab Methylcobalamin 1500 mcg", "Mecobalamin", "Supplement", "strip of 10", 85, 95, 25),
        ("Ortho knee cap (L)", "—", "Appliance", "piece", 350, 25, 8),
        ("Lumbar support belt", "—", "Appliance", "piece", 650, 18, 6),
        ("Cervical collar (M)", "—", "Appliance", "piece", 420, 15, 5),
        ("Crepe bandage 10 cm", "—", "Consumable", "roll", 60, 110, 30),
        ("Plaster of Paris 15 cm", "POP bandage", "Consumable", "roll", 95, 55, 20),
        ("Syringe 5 ml", "—", "Consumable", "piece", 6, 400, 100),
        ("IV set with cannula", "—", "Consumable", "set", 45, 90, 30),
    ]
    medicines: list[Medicine] = []
    for name, gen, cat, unit, price, qty, reorder in med_rows:
        m = Medicine(name=name, generic_name=gen, category=cat,
                     manufacturer="Sun Pharma" if rng.random() < .5 else "Cipla",
                     unit=unit, unit_price=price, stock_quantity=qty,
                     reorder_level=reorder, batch_number=f"B{rng.randint(1000,9999)}",
                     expiry_date=today + timedelta(days=rng.randint(200, 900)))
        db.add(m)
        medicines.append(m)
    await db.flush()
    for m in medicines:
        db.add(StockTransaction(
            medicine_id=m.id, txn_type=StockTxnType.IN, quantity=m.stock_quantity,
            balance_after=m.stock_quantity, reference="Opening stock",
            performed_by_user_id=1,
            created_at=_dt(rng.randint(60, 120), 10)))
    # make two items visibly low for the alert widget
    medicines[13].stock_quantity = 5
    medicines[20].stock_quantity = 2

    # -------------------------------------------------------------- rooms & OT
    rooms: list[Room] = []
    def add_rooms(prefix, floor, count, rtype):
        for i in range(1, count + 1):
            r = Room(room_number=f"{prefix}{floor}0{i}", room_type=rtype,
                     daily_rate=ROOM_RATES[rtype.value], floor=floor)
            db.add(r)
            rooms.append(r)
    add_rooms("E", 1, 6, RoomType.ECONOMY)
    add_rooms("D", 2, 4, RoomType.DELUXE)
    add_rooms("V", 3, 2, RoomType.VIP)
    add_rooms("ICU-", 1, 2, RoomType.ICU)
    ot1 = OperationTheatre(name="OT-1 (Major)", category=OTCategory.MAJOR,
                           equipment="C-arm; laminar airflow; anaesthesia workstation; diathermy")
    ot2 = OperationTheatre(name="OT-2 (Minor)", category=OTCategory.MINOR,
                           equipment="Phaco machine; operating microscope; autoclave")
    db.add_all([ot1, ot2])
    await db.flush()

    # ------------------------------------------------- consultations & billing
    services = flat_service_names()
    ortho_dx = ["Knee osteoarthritis", "Lumbar spondylosis", "Frozen shoulder",
                "Fracture — distal radius", "Cervical radiculopathy",
                "Plantar fasciitis", "Ligament sprain — ankle"]
    eye_dx = ["Immature cataract", "Dry eye syndrome", "Refractive error",
              "Conjunctivitis", "Early glaucoma", "Diabetic retinopathy screening"]

    consult_count = 0
    for days_ago in range(120, -1, -1):
        d = today - timedelta(days=days_ago)
        if d.weekday() == 6:      # Sunday closed
            continue
        for _ in range(rng.randint(1, 4)):
            doctor = sameer if rng.random() < 0.6 else lalan
            dept = (Department.ORTHOPAEDICS if doctor is sameer
                    else Department.OPHTHALMOLOGY)
            dx = rng.choice(ortho_dx if doctor is sameer else eye_dx)
            p = rng.choice(patients)
            fee = CONSULTATION_FEES["sameer" if doctor is sameer else "lalan"]
            visited = datetime.combine(d, time(rng.randint(11, 17), rng.choice((0, 30))))
            c = Consultation(
                patient_id=p.id, doctor_id=doctor.id, department=dept,
                visited_at=visited,
                chief_complaint=f"{dx.split(' —')[0]} — pain/vision complaint",
                diagnosis=dx,
                clinical_notes="Examined; advised rest and review.",
                treatments_given=rng.choice(services), fee=fee,
                follow_up_on=d + timedelta(days=rng.choice((7, 10, 14)))
                if rng.random() < 0.35 else None)
            db.add(c)
            await db.flush()
            consult_count += 1

            bill = Bill(bill_number=bill_number(), bill_type=BillType.OPD,
                        patient_id=p.id, consultation_id=c.id, subtotal=fee,
                        total=fee, generated_at=visited)
            db.add(bill)
            await db.flush()
            db.add(BillItem(bill_id=bill.id,
                            category=BillItemCategory.CONSULTATION,
                            description=f"Consultation — {doctor.full_name}",
                            quantity=1, unit_price=fee, amount=fee))

            # prescription for ~60% of visits
            rx = None
            if rng.random() < 0.6:
                rx = Prescription(consultation_id=c.id, patient_id=p.id,
                                  doctor_id=doctor.id,
                                  notes="Take after food.",
                                  created_at=visited)
                db.add(rx)
                await db.flush()
                pool = medicines[:11] if doctor is sameer else medicines[11:16]
                rx_total = 0
                for med in rng.sample(pool, rng.randint(1, 3)):
                    qty = rng.randint(1, 2)
                    db.add(PrescriptionItem(
                        prescription_id=rx.id, medicine_id=med.id,
                        medicine_name=med.name, dosage="1-0-1",
                        frequency="Twice a day", duration_days=5, quantity=qty,
                        instructions="After food"))
                    rx_total += med.unit_price * qty
                # dispense (and bill) for most older prescriptions
                if days_ago > 1 and rng.random() < 0.85:
                    rx.dispensed = True
                    rx.dispensed_at = visited + timedelta(minutes=25)
                    for item in [*(await db.execute(
                            select(PrescriptionItem).where(
                                PrescriptionItem.prescription_id == rx.id)
                    )).scalars()]:
                        med = next(m for m in medicines
                                   if m.id == item.medicine_id)
                        amount = med.unit_price * item.quantity
                        db.add(BillItem(
                            bill_id=bill.id,
                            category=BillItemCategory.MEDICINE,
                            description=f"{med.name} ({med.unit})",
                            quantity=item.quantity, unit_price=med.unit_price,
                            amount=amount))
                        bill.subtotal += amount
                        bill.total = bill.subtotal

            if days_ago > 0 or rng.random() < 0.5:
                bill.status = BillStatus.PAID
                bill.payment_mode = rng.choice(
                    ["UPI", "CASH", "CARD"])  # type: ignore[assignment]
                bill.transaction_ref = txn_reference()
                bill.paid_at = visited + timedelta(hours=1)

    # ------------------------------------------------------ historic admission
    async def make_admission(patient, room, doctor, nurse, days_ago_in,
                             stay_hours, adm_type, reason, dx, surgery=None):
        admitted = _dt(days_ago_in, 10)
        a = Admission(patient_id=patient.id, room_id=room.id,
                      primary_doctor_id=doctor.id, assigned_nurse_id=nurse.id,
                      admission_type=adm_type, reason=reason, diagnosis=dx,
                      admitted_at=admitted, created_by_user_id=1)
        db.add(a)
        await db.flush()
        claim = Mediclaim(claim_number=claim_number(), admission_id=a.id,
                          patient_id=patient.id, insurer_name="Star Health",
                          policy_number=f"SH-{rng.randint(10**7, 10**8-1)}")
        db.add(claim)

        # care timeline
        t = admitted + timedelta(hours=2)
        med_total = 0
        visits = 0
        end = admitted + timedelta(hours=stay_hours)
        while t < end:
            kind = rng.random()
            if kind < 0.35:
                med = rng.choice(medicines[:11])
                qty = 1
                charge = med.unit_price * qty
                med_total += charge
                db.add(CareLog(admission_id=a.id,
                               log_type=CareLogType.MEDICATION,
                               description=f"Administered {med.name}",
                               medicine_id=med.id, quantity=qty, charge=charge,
                               logged_at=t, logged_by_user_id=nurse.user_id))
            elif kind < 0.5:
                visits += 1
                db.add(CareLog(admission_id=a.id,
                               log_type=CareLogType.DOCTOR_VISIT,
                               description="Ward round — progress reviewed",
                               doctor_id=doctor.id, charge=0, logged_at=t,
                               logged_by_user_id=nurse.user_id))
            elif kind < 0.65:
                db.add(CareLog(admission_id=a.id, log_type=CareLogType.VITALS,
                               description=f"BP {rng.randint(110,135)}/"
                                           f"{rng.randint(70,88)} · "
                                           f"Pulse {rng.randint(68,92)} · "
                                           f"SpO₂ {rng.randint(96,99)}%",
                               logged_at=t, logged_by_user_id=nurse.user_id))
            elif kind < 0.8:
                db.add(CareLog(admission_id=a.id, log_type=CareLogType.MEAL,
                               description=rng.choice(
                                   ("Breakfast served", "Lunch — diabetic diet",
                                    "Dinner served")),
                               logged_at=t, logged_by_user_id=nurse.user_id))
            else:
                db.add(CareLog(admission_id=a.id, log_type=CareLogType.NOTE,
                               description="Patient comfortable; no fresh complaints.",
                               logged_at=t, logged_by_user_id=nurse.user_id))
        # ensure at least some doctor visits carry the ward-visit charge
            t += timedelta(hours=rng.randint(3, 6))
        if visits == 0:
            visits = 1
            db.add(CareLog(admission_id=a.id, log_type=CareLogType.DOCTOR_VISIT,
                           description="Ward round", doctor_id=doctor.id,
                           charge=0, logged_at=admitted + timedelta(hours=5),
                           logged_by_user_id=nurse.user_id))

        surgery_charges = 0
        if surgery:
            s = Surgery(theatre_id=ot1.id, patient_id=patient.id,
                        admission_id=a.id, surgeon_id=doctor.id, name=surgery,
                        scheduled_at=admitted + timedelta(hours=20),
                        started_at=admitted + timedelta(hours=20),
                        ended_at=admitted + timedelta(hours=22, minutes=30),
                        status=SurgeryStatus.COMPLETED,
                        equipment_used="C-arm; implant set; diathermy",
                        charges=OT_BASE_CHARGES["MAJOR"],
                        notes="Uneventful; implant in situ.")
            db.add(s)
            surgery_charges = s.charges

        # discharge + bill (mirrors WardService.discharge math)
        import math as _m
        discharged = end
        total_hours = max(1, _m.ceil(stay_hours))
        billable_days = _m.ceil(total_hours / 24)
        bill = Bill(bill_number=bill_number(), bill_type=BillType.IPD,
                    patient_id=patient.id, admission_id=a.id,
                    generated_at=discharged,
                    notes=f"Stay of {total_hours} h across {billable_days} day(s)")
        db.add(bill)
        await db.flush()
        subtotal = 0

        def item(cat, desc, qty, unit):
            nonlocal subtotal
            amt = qty * unit
            db.add(BillItem(bill_id=bill.id, category=cat, description=desc,
                            quantity=qty, unit_price=unit, amount=amt))
            subtotal += amt

        from app.core.constants import (ADMISSION_CHARGE, DOCTOR_VISIT_CHARGE,
                                        EMERGENCY_CHARGE,
                                        NURSING_CHARGE_PER_DAY)
        item(BillItemCategory.ADMISSION, "Admission & registration", 1,
             ADMISSION_CHARGE)
        if adm_type == AdmissionType.EMERGENCY:
            item(BillItemCategory.EMERGENCY, "Emergency / casualty care", 1,
                 EMERGENCY_CHARGE)
        item(BillItemCategory.ROOM,
             f"Room {room.room_number} ({room.room_type.value}) · {total_hours} h",
             billable_days, room.daily_rate)
        item(BillItemCategory.NURSING, "Nursing care", billable_days,
             NURSING_CHARGE_PER_DAY)
        if visits:
            item(BillItemCategory.DOCTOR_VISIT, "Doctor ward visits", visits,
                 DOCTOR_VISIT_CHARGE)
        if med_total:
            item(BillItemCategory.MEDICINE, "Medicines administered in ward",
                 1, med_total)
        if surgery_charges:
            item(BillItemCategory.OT, f"Operation theatre — {surgery}", 1,
                 surgery_charges)
        bill.subtotal = subtotal
        bill.total = subtotal
        bill.status = BillStatus.PAID
        bill.payment_mode = "UPI"  # type: ignore[assignment]
        bill.transaction_ref = txn_reference()
        bill.paid_at = discharged + timedelta(hours=2)

        a.status = AdmissionStatus.DISCHARGED
        a.discharged_at = discharged
        a.discharge_summary = ("Treated, stable at discharge. "
                               "Medications and review advised.")
        claim.status = ClaimStatus.FINALIZED
        claim.finalized_at = discharged
        await db.flush()
        import json as _json
        claim.summary_json = _json.dumps({
            "patient": {"code": patient.patient_code,
                        "name": patient.full_name, "age": patient.age,
                        "sex": patient.sex.value},
            "admission": {"type": adm_type.value, "reason": reason,
                          "diagnosis": dx,
                          "admitted_at": admitted.isoformat(),
                          "discharged_at": discharged.isoformat(),
                          "hours": total_hours,
                          "room": f"{room.room_number} ({room.room_type.value})",
                          "primary_doctor": doctor.full_name},
            "bill": {"number": bill.bill_number, "subtotal": bill.subtotal,
                     "discount": 0, "total": bill.total,
                     "items": [{"category": i.category.value,
                                "description": i.description,
                                "quantity": i.quantity, "amount": i.amount}
                               for i in (await db.execute(
                                   select(BillItem).where(
                                       BillItem.bill_id == bill.id)
                               )).scalars()]},
            "discharge_summary": a.discharge_summary,
        }, indent=2)
        return a

    await make_admission(patients[0], rooms[6], sameer, anita, 45, 74,
                         AdmissionType.PLANNED,
                         "Total knee replacement — left",
                         "Grade IV knee osteoarthritis",
                         surgery="Total knee replacement (left)")
    await make_admission(patients[4], rooms[12], sameer, kavita, 20, 52,
                         AdmissionType.EMERGENCY,
                         "Fall at home — hip pain",
                         "Intertrochanteric fracture femur",
                         surgery="PFN fixation — right femur")
    await make_admission(patients[1], rooms[1], lalan, anita, 10, 26,
                         AdmissionType.PLANNED, "Cataract surgery — right eye",
                         "Immature senile cataract",
                         surgery=None)

    # one live admission right now (economy) + one live emergency (ICU)
    live1 = Admission(patient_id=patients[6].id, room_id=rooms[2].id,
                      primary_doctor_id=sameer.id, assigned_nurse_id=kavita.id,
                      admission_type=AdmissionType.PLANNED,
                      reason="ACL reconstruction — post-op care",
                      diagnosis="ACL tear (right knee)",
                      admitted_at=datetime.now() - timedelta(hours=30),
                      created_by_user_id=1)
    live2 = Admission(patient_id=patients[8].id, room_id=rooms[13].id,
                      primary_doctor_id=sameer.id, assigned_nurse_id=anita.id,
                      admission_type=AdmissionType.EMERGENCY,
                      reason="RTA — observation",
                      diagnosis="Head injury ruled out; rib contusion",
                      admitted_at=datetime.now() - timedelta(hours=7),
                      created_by_user_id=1)
    db.add_all([live1, live2])
    rooms[2].status = RoomStatus.OCCUPIED
    rooms[13].status = RoomStatus.OCCUPIED
    await db.flush()
    for adm in (live1, live2):
        db.add(Mediclaim(claim_number=claim_number(), admission_id=adm.id,
                         patient_id=adm.patient_id))
        db.add(CareLog(admission_id=adm.id, log_type=CareLogType.VITALS,
                       description="BP 122/80 · Pulse 78 · SpO₂ 98%",
                       logged_at=datetime.now() - timedelta(hours=2),
                       logged_by_user_id=anita.user_id))
        db.add(CareLog(admission_id=adm.id, log_type=CareLogType.DOCTOR_VISIT,
                       description="Morning round — stable",
                       doctor_id=sameer.id, charge=0,
                       logged_at=datetime.now() - timedelta(hours=4),
                       logged_by_user_id=anita.user_id))
        db.add(Reminder(title=f"Admitted — {next(p.full_name for p in patients if p.id == adm.patient_id)}",
                        message=f"Active stay · {adm.reason}",
                        category=(ReminderCategory.EMERGENCY
                                  if adm.admission_type == AdmissionType.EMERGENCY
                                  else ReminderCategory.ADMISSION),
                        patient_id=adm.patient_id, admission_id=adm.id,
                        due_at=datetime.now(), created_by_user_id=1))

    # scheduled surgery tomorrow in OT-1
    db.add(Surgery(theatre_id=ot1.id, patient_id=patients[6].id,
                   admission_id=live1.id, surgeon_id=sameer.id,
                   name="ACL reconstruction (right knee)",
                   scheduled_at=datetime.combine(today + timedelta(days=1),
                                                 time(9, 30)),
                   charges=OT_BASE_CHARGES["MAJOR"],
                   equipment_used="Arthroscopy tower; graft set"))

    # ------------------------------------------------------------------ physio
    plan = PhysioPlan(
        patient_id=patients[0].id, prescribed_by_id=sameer.id, days_count=10,
        exercises="; ".join([PhysioExercise.KNEE_LEFT.value,
                             PhysioExercise.CORE_STRENGTHENING.value,
                             PhysioExercise.LS_SPINE_STRENGTHENING.value]),
        modalities="; ".join([PhysioModality.IFT.value, PhysioModality.US.value]),
        traction="", notes="Post-TKR rehabilitation protocol.",
        prescribed_on=_dt(40, 12))
    db.add(plan)
    await db.flush()
    for i in range(7):
        db.add(PhysioSession(plan_id=plan.id,
                             session_date=today - timedelta(days=38 - i * 2),
                             timing=f"{9 + (i % 3)}:00 AM",
                             amount=PHYSIO_SESSION_CHARGE,
                             performed_by_id=rohan_pt.id,
                             notes="Tolerated well."))
    plan2 = PhysioPlan(
        patient_id=patients[3].id, prescribed_by_id=sameer.id, days_count=6,
        exercises="; ".join([PhysioExercise.SHOULDER_MOB_RIGHT.value,
                             PhysioExercise.CERVICAL_SPINE_STRENGTHENING.value]),
        modalities=PhysioModality.SWD.value,
        traction=PhysioTraction.CERVICAL.value,
        notes="Cervical spondylosis — traction 10 min.",
        prescribed_on=_dt(5, 12))
    db.add(plan2)
    await db.flush()
    for i in range(2):
        db.add(PhysioSession(plan_id=plan2.id,
                             session_date=today - timedelta(days=3 - i),
                             timing="6:30 PM", amount=PHYSIO_SESSION_CHARGE,
                             performed_by_id=rohan_pt.id))

    # ------------------------------------------------------------ appointments
    def appt_days():
        for offset in (0, 1):
            d = today + timedelta(days=offset)
            if d.weekday() != 6:
                yield d
    slot_pool = ["11:00", "11:30", "12:00", "12:30", "16:00", "16:30",
                 "17:00", "18:30", "19:00"]
    for d in appt_days():
        used: set[tuple[int, str]] = set()
        for _ in range(5):
            doc = sameer if rng.random() < 0.6 else lalan
            pool = slot_pool if doc is sameer else slot_pool[:7]
            slot = rng.choice(pool)
            if (doc.id, slot) in used:
                continue
            used.add((doc.id, slot))
            p = rng.choice(patients)
            via = rng.choice([BookedVia.PORTAL, BookedVia.GUEST,
                              BookedVia.WALK_IN])
            db.add(Appointment(
                code=appointment_code(),
                patient_id=p.id if via != BookedVia.GUEST else None,
                guest_name=p.full_name if via == BookedVia.GUEST else "",
                guest_phone=p.phone if via == BookedVia.GUEST else "",
                doctor_id=doc.id,
                department=(Department.ORTHOPAEDICS if doc is sameer
                            else Department.OPHTHALMOLOGY),
                appointment_date=d, slot=slot,
                reason="Pain / review" if doc is sameer else "Vision check",
                status=AppointmentStatus.BOOKED, booked_via=via))

    # -------------------------------------------------------------- attendance
    for s in staff_objs.values():
        for days_ago in range(120, -1, -1):
            d = today - timedelta(days=days_ago)
            if d < s.date_joined or d.weekday() == 6:
                continue
            roll = rng.random()
            if roll < 0.06:
                db.add(Attendance(staff_id=s.id, day=d,
                                  status=AttendanceStatus.ABSENT))
                continue
            if roll < 0.10:
                db.add(Attendance(staff_id=s.id, day=d,
                                  status=AttendanceStatus.LEAVE,
                                  note="Approved leave"))
                continue
            sh, sm = (int(x) for x in s.shift_start.split(":"))
            eh, em = (int(x) for x in s.shift_end.split(":"))
            cin = datetime.combine(d, time(sh, sm)) + timedelta(
                minutes=rng.randint(-10, 25))
            cout = datetime.combine(d, time(eh, em)) + timedelta(
                minutes=rng.randint(-20, 40))
            if days_ago == 0:
                cout = None
            hours = (round((cout - cin).total_seconds() / 3600, 2)
                     if cout else 0.0)
            status = (AttendanceStatus.HALF_DAY
                      if cout and hours < 4 else AttendanceStatus.PRESENT)
            db.add(Attendance(staff_id=s.id, day=d, check_in=cin,
                              check_out=cout, hours_worked=hours,
                              status=status))

    # ----------------------------------------------------------------- payroll
    for back in range(1, 4):
        m = today.month - back
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        for s in staff_objs.values():
            if date(y, m, 1) < s.date_joined.replace(day=1):
                continue
            db.add(SalaryPayment(
                staff_id=s.id, month=m, year=y, amount=s.monthly_salary,
                mode=PayrollMode.AUTOPAY, reference=payment_reference(),
                paid_on=datetime(y, m, 28, 18, 0)
                if m != today.month else datetime.now(),
                paid_by_user_id=1))

    # ----------------------------------------------------- reminders (general)
    db.add(Reminder(title="Order Timolol eye drops",
                    message="Stock below reorder level (5 left).",
                    category=ReminderCategory.GENERAL,
                    due_at=datetime.now() + timedelta(hours=4),
                    created_by_user_id=1))
    db.add(Reminder(title="AMC — autoclave service",
                    message="Quarterly service visit due this week.",
                    category=ReminderCategory.GENERAL,
                    due_at=datetime.combine(today + timedelta(days=2),
                                            time(10, 0)),
                    created_by_user_id=1))

    # ----------------------------------------------------- documents (X-rays)
    docs = _make_placeholder_scans()
    for (pat_idx, dtype, title, rel, size), days_ago in zip(
            docs, (44, 44, 19, 9)):
        db.add(PatientDocument(
            patient_id=patients[pat_idx].id, doc_type=dtype, title=title,
            file_path=rel, original_name=rel.split("/")[-1],
            content_type="image/png", size_bytes=size,
            taken_on=today - timedelta(days=days_ago),
            notes="Seeded demo scan.", uploaded_by_user_id=1,
            uploaded_at=_dt(days_ago, 13)))

    await db.commit()
    print(f"[seed] Demo data created — {consult_count} consultations, "
          f"{len(patients)} patients, {len(medicines)} medicines.")


def _make_placeholder_scans() -> list[tuple[int, DocumentType, str, str, int]]:
    """Generate grey 'X-ray' style placeholder PNGs inside UPLOAD_DIR."""
    from pathlib import Path

    from PIL import Image, ImageDraw

    from app.core.config import get_settings

    root = Path(get_settings().UPLOAD_DIR)
    specs = [
        (0, DocumentType.XRAY, "X-ray — left knee (AP view)", "xray_knee.png"),
        (0, DocumentType.XRAY, "X-ray — left knee (lateral)", "xray_knee_lat.png"),
        (4, DocumentType.XRAY, "X-ray — right hip (post-op)", "xray_hip.png"),
        (1, DocumentType.LAB_REPORT, "Biometry report — right eye", "biometry.png"),
    ]
    out = []
    for pat_idx, dtype, title, fname in specs:
        rel = Path(f"patient_{pat_idx + 1}") / fname
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("L", (640, 480), 18)
        d = ImageDraw.Draw(img)
        for i in range(40, 600, 24):
            d.line([(i, 60), (i + 30, 420)], fill=55 + (i % 60), width=6)
        d.ellipse([220, 140, 420, 360], outline=170, width=8)
        d.text((20, 12), "DR. PALASKAR HOSPITAL — DEMO SCAN", fill=220)
        d.text((20, 450), title, fill=200)
        img.save(dest)
        out.append((pat_idx, dtype, title, rel.as_posix(),
                    dest.stat().st_size))
    return out
