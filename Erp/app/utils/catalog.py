"""Hard-coded hospital catalogue (per management-supplied content).

This is the single source of truth for the public website and for the
"treatments/services" pickers inside consultations and care logs.
"""
from __future__ import annotations

from app.core.constants import HOSPITAL
from app.models.enums import PhysioExercise, PhysioModality, PhysioTraction

DOCTORS_PUBLIC = [
    {
        "name": "Dr. Sameer B. Palaskar",
        "username": "sameer",
        "qualification": "D.N.B (ORTHO), D.Ortho, M.N.A.M.S.",
        "title": "Consultant Orthopaedic Surgeon (Trauma, Spine & Joint Replacement)",
        "department": "ORTHOPAEDICS",
        "opd_hours": "11:00 AM – 9:00 PM",
    },
    {
        "name": "Dr. Mrs. Lalan Palaskar",
        "username": "lalan",
        "qualification": "M.B.B.S, D.O.M.S.",
        "title": "Consultant Eye Surgeon",
        "department": "OPHTHALMOLOGY",
        "opd_hours": "11:00 AM – 6:00 PM",
    },
]

FACILITIES = [
    "24-hr accident & fracture care",
    "300 MA High Frequency Rotating Anode X-Ray Machine",
    "Latest & Advanced Konica Minolta DR (Digital X-Ray) System",
    "Laminar Air-Flow & HEPA Filter system",
    "Latest & Advanced Siemens 5C C-arm machine",
    "Powered bone drill & saw systems",
    "Advanced, latest protocol & system for major bone & joint surgeries",
    "Flowtron anti-DVT prophylaxis machines",
    "Spacious & well-ventilated wards & special rooms",
    "Well-equipped surgical ICU",
    "Lift; 62.5 kv generator facility",
    "High-efficiency horizontal autoclave machine",
    "Stryker T5 surgical helmets & hoods",
    "Operative microscope",
    "5-step slit lamp",
]

EXPERT_CONSULTATION = {
    "ORTHOPAEDICS": [
        "Artificial joint replacement surgery",
        "Simple & complex fractures",
        "Slipped disc & other spine problems",
        "Arthroscopic joint surgery",
        "Rheumatoid & old-age arthritis",
        "Advanced orthopaedic surgery techniques",
        "Tibial plateau fracture fixation",
        "PFNA-2 / Nailing",
        "Hip joint replacement",
        "Knee joint replacement",
        "Spine surgery",
    ],
    "OPHTHALMOLOGY": [
        "Common eye diseases & refraction errors",
        "Eye surgeries",
        "Cataract operation",
        "Squint correction",
    ],
}

# 14 treatment programmes — each with its detailed sub-services -------------
TREATMENTS = [
    {"slug": "orthopedic-trauma", "name": "Orthopedic Trauma",
     "blurb": "Fractures, dislocations, joint injuries and complex bone damage from accidents, sports injuries or falls. A 24/7 trauma team with rapid diagnosis and prompt treatment prevents complications and restores mobility quickly and safely — digital X-rays, fully equipped operation theatres and personalised, compassionate care.",
     "items": [
         ("Emergency Fracture Management", "Quick stabilization and treatment for all fracture types"),
         ("Complex Bone & Joint Injury Care", "Specialized care for multiple fractures and severe injuries"),
         ("Minimally Invasive Fixation", "Advanced surgical techniques for faster recovery and less pain"),
         ("Post-Trauma Rehabilitation", "Physiotherapy and guided exercises for strength and flexibility"),
         ("Pediatric Trauma Care", "Gentle, effective treatment for children's bone injuries"),
     ]},
    {"slug": "paediatric-orthopaedics", "name": "Paediatric Orthopaedics",
     "blurb": "Diagnosis, treatment and management of bone, joint and muscle conditions in children — newborn to teenager. Developing bones need care distinct from adult orthopaedics: medical excellence with child-friendly comfort.",
     "items": [
         ("Fracture & Injury Care", "Gentle, effective treatment for broken bones and sports injuries"),
         ("Congenital Orthopaedic Disorders", "Clubfoot, hip dysplasia and limb deformities"),
         ("Growth-Related Bone Problems", "Early detection and treatment of growth-plate injuries and alignment issues"),
         ("Spinal Deformities", "Scoliosis, kyphosis and other spinal conditions in children"),
         ("Paediatric Rehabilitation", "Physiotherapy tailored to a child's healing and development needs"),
     ]},
    {"slug": "foot-ankle-surgery", "name": "Foot and Ankle Surgery",
     "blurb": "Injuries, deformities and chronic conditions of the lower limbs — sports injuries, accidents, arthritis or congenital problems. Advanced techniques restore mobility, reduce pain and improve quality of life.",
     "items": [
         ("Fracture & Trauma Management", "Surgical repair of broken bones in the foot and ankle"),
         ("Ligament & Tendon Repair", "Sprains, tears and sports-related injuries"),
         ("Arthroscopy & Minimally Invasive Surgery", "Faster recovery, smaller incisions, less discomfort"),
         ("Correction of Deformities", "Bunions, flat feet and misalignments"),
         ("Arthritis & Joint Replacement", "Pain relief and improved movement for worn-out joints"),
         ("Post-Surgery Rehabilitation", "Physiotherapy and guided exercises for safe recovery"),
     ]},
    {"slug": "shoulder-elbow-surgery", "name": "Shoulder and Elbow Surgery",
     "blurb": "Injuries, degenerative conditions and movement disorders of the upper limb. Modern surgical and minimally invasive techniques restore function, relieve pain and help patients return to daily activities with confidence.",
     "items": [
         ("Fracture & Trauma Repair", "Surgical management of broken or dislocated shoulder and elbow joints"),
         ("Arthroscopy (Keyhole Surgery)", "Rotator cuff tears, labral injuries and joint clean-up"),
         ("Ligament & Tendon Repair", "Sports injuries and overuse conditions"),
         ("Joint Replacement Surgery", "Shoulder and elbow arthroplasty for severe arthritis or joint damage"),
         ("Correction of Deformities", "Surgical alignment for congenital or post-injury deformities"),
         ("Post-Operative Rehabilitation", "Physiotherapy for safe, gradual restoration of movement and strength"),
     ]},
    {"slug": "ganglion-cyst-removal", "name": "Ganglion Cyst Removal",
     "blurb": "Fluid-filled lumps commonly at the wrist, hand, ankle or foot. Often harmless, but can cause pain, discomfort or limited movement — safe, effective surgical removal offers lasting relief.",
     "items": [
         ("Accurate Diagnosis", "Clinical evaluation and imaging to confirm the cyst's nature and location"),
         ("Minimally Invasive Surgery", "Small incisions, quicker healing, minimal scarring"),
         ("Complete Cyst Removal", "Cyst and its root removed to reduce recurrence"),
         ("Pain Management & Aftercare", "Gentle post-surgery care for comfort and proper healing"),
         ("Rehabilitation Support", "Physiotherapy guidance if required, restoring joint mobility"),
     ]},
    {"slug": "carpal-tunnel-release", "name": "Carpal Tunnel Release",
     "blurb": "Relief for hand numbness, tingling and pain caused by Carpal Tunnel Syndrome (median nerve compression at the wrist). Precise surgical techniques restore comfort and function.",
     "items": [
         ("Accurate Diagnosis", "Detailed evaluation with nerve conduction studies and imaging"),
         ("Minimally Invasive Techniques", "Smaller incisions, faster healing, less discomfort"),
         ("Open & Endoscopic Surgery Options", "Tailored approach based on patient needs"),
         ("Pain Relief & Functional Recovery", "Reduced nerve pressure restores normal hand movement"),
         ("Post-Surgery Rehabilitation", "Physiotherapy support to regain strength and flexibility"),
     ]},
    {"slug": "tendon-ligament-reconstruction", "name": "Tendon and Ligament Reconstruction",
     "blurb": "Restores stability, movement and strength after injuries from sports, accidents or overuse. When tendons or ligaments are torn or severely damaged, surgical reconstruction regains full mobility.",
     "items": [
         ("Sports Injury Repair", "Reconstruction of torn ACL, PCL, MCL, rotator cuff, Achilles tendon and more"),
         ("Minimally Invasive Techniques", "Arthroscopic and advanced surgical methods for faster recovery"),
         ("Trauma & Accident Repairs", "Restoring function after severe injuries"),
         ("Chronic Tear Management", "Surgical solutions for long-standing tendon and ligament damage"),
         ("Rehabilitation & Physiotherapy", "Customized post-surgery recovery programmes for strength and flexibility"),
     ]},
    {"slug": "osteotomy", "name": "Osteotomy",
     "blurb": "Corrects bone deformities, realigns joints and improves mobility by cutting and reshaping bone — relieving pain, restoring alignment and delaying or preventing joint replacement. Commonly performed for knee/hip arthritis, leg-length differences and bone misalignment.",
     "items": [
         ("Knee & Hip Osteotomy", "Realignment to reduce pressure on damaged joints"),
         ("Upper & Lower Limb Deformity Correction", "Surgical adjustment for proper balance and mobility"),
         ("Arthritis Management", "Pain relief and improved function without immediate joint replacement"),
         ("Post-Fracture Bone Realignment", "Correcting improper bone healing after trauma"),
         ("Comprehensive Rehabilitation", "Guided physiotherapy for safe, steady recovery"),
     ]},
    {"slug": "soft-tissue-repair", "name": "Soft Tissue Repair",
     "blurb": "Injuries involving muscles, tendons, ligaments and skin — from accidents, sports injuries, overuse or degenerative conditions causing pain, swelling and loss of function. Precise surgical techniques restore normal structure and movement.",
     "items": [
         ("Sports Injury Repair", "Surgical treatment for torn ligaments, tendons or muscle ruptures"),
         ("Trauma-Related Repairs", "Reconstruction after accidents or severe injuries"),
         ("Minimally Invasive Procedures", "Smaller incisions, faster recovery, less scarring"),
         ("Reattachment of Torn Structures", "Restoring function through tendon, ligament or muscle repair"),
         ("Post-Surgery Rehabilitation", "Physiotherapy for strength, flexibility and a safe return to activity"),
     ]},
    {"slug": "sports-medicine", "name": "Sports Medicine",
     "blurb": "Diagnosis, treatment and prevention of sports-related injuries — sudden trauma or repetitive strain — helping athletes and active individuals return to peak performance with faster recovery and long-term joint health.",
     "items": [
         ("Arthroscopic Surgery", "Keyhole procedures for knee, shoulder, ankle and hip injuries"),
         ("Ligament & Tendon Reconstruction", "Repair of ACL, PCL, rotator cuff, Achilles tendon and more"),
         ("Fracture & Joint Injury Management", "Treatment for bone breaks, dislocations and cartilage damage"),
         ("Meniscus & Cartilage Repair", "Restoring smooth joint movement for pain-free activity"),
         ("Post-Surgical Rehabilitation", "Sports-specific physiotherapy to rebuild strength, flexibility and endurance"),
     ]},
    {"slug": "spinal-surgery", "name": "Spinal Surgery",
     "blurb": "Conditions affecting the neck, back and spine — from chronic back pain to severe spinal injuries. The latest surgical techniques relieve pain, restore mobility and improve quality of life.",
     "items": [
         ("Disc Surgery", "Removal or repair of herniated / slipped discs to relieve nerve pressure"),
         ("Spinal Decompression", "Relieving pressure on the spinal cord and nerves caused by stenosis or bone spurs"),
         ("Spinal Fusion", "Stabilizing the spine for fractures, deformities or degenerative disc disease"),
         ("Minimally Invasive Spine Surgery", "Smaller incisions, faster recovery, less post-operative discomfort"),
         ("Scoliosis & Deformity Correction", "Surgical alignment for abnormal spinal curves"),
         ("Trauma & Fracture Management", "Treatment of spinal injuries from accidents or falls"),
     ]},
    {"slug": "fracture-repair", "name": "Fracture Repair",
     "blurb": "Treatment of broken bones with quick, safe restoration of normal function. Advanced surgical techniques ensure precise bone alignment, stable fixation and faster healing.",
     "items": [
         ("Emergency Fracture Management", "Prompt stabilization and treatment to prevent complications"),
         ("Open Reduction & Internal Fixation (ORIF)", "Plates, screws or rods hold bones in place during healing"),
         ("Minimally Invasive Fixation", "Smaller incisions for reduced pain and quicker recovery"),
         ("Complex & Multiple Fracture Care", "Specialized treatment for severe injuries involving multiple bones"),
         ("Paediatric Fracture Surgery", "Gentle, age-appropriate care for children's bone injuries"),
         ("Post-Surgery Rehabilitation", "Physiotherapy to restore strength, movement and flexibility"),
     ]},
    {"slug": "arthroscopy", "name": "Arthroscopy",
     "blurb": "Minimally invasive diagnosis and treatment of joint problems: a small camera gives a clear internal view, allowing precise repairs through tiny incisions — faster recovery, less pain, minimal scarring versus open surgery.",
     "items": [
         ("Knee Arthroscopy", "Meniscus tears, ACL/PCL injuries and cartilage damage"),
         ("Shoulder Arthroscopy", "Rotator cuff tears, labral injuries and shoulder impingement"),
         ("Ankle Arthroscopy", "Ligament injuries, cartilage damage and bone spurs"),
         ("Hip Arthroscopy", "Labral tears, impingement and loose bodies"),
         ("Joint Debridement & Cleaning", "Removal of loose fragments and inflamed tissue for smooth movement"),
         ("Sports Injury Management", "Quick, effective treatment for athletes and active individuals"),
     ]},
    {"slug": "joint-replacement", "name": "Joint Replacement Surgery",
     "blurb": "Relieves pain, restores mobility and improves quality of life for severe joint damage from arthritis, injury or degenerative conditions. Advanced techniques and high-quality implants ensure long-lasting results and smoother recovery.",
     "items": [
         ("Knee Replacement Surgery", "Total and partial knee replacements for arthritis or injury-related damage"),
         ("Hip Replacement Surgery", "Restoring hip movement and reducing pain from joint degeneration"),
         ("Shoulder Replacement Surgery", "Replacing damaged shoulder joints for improved arm function"),
         ("Revision Joint Replacement", "Correcting or replacing failed or worn-out implants"),
         ("Minimally Invasive Techniques", "Smaller incisions for faster healing and reduced discomfort"),
         ("Comprehensive Rehabilitation", "Physiotherapy and guided exercises to regain strength and flexibility"),
     ]},
]

PHYSIO = {
    "hours": "Mon–Sat · 11 AM–1 PM & 5 PM–9 PM · Sunday closed",
    "exercises": [e.value for e in PhysioExercise],
    "modalities": [m.value for m in PhysioModality],
    "traction": [t.value for t in PhysioTraction],
    "protocol": "The doctor prescribes the number of days and specifies which "
                "exercises, modalities and traction apply; each session's date, "
                "amount and timing are recorded per patient.",
}


def public_info() -> dict:
    return {
        "hospital": HOSPITAL,
        "doctors": DOCTORS_PUBLIC,
        "facilities": FACILITIES,
        "expert_consultation": EXPERT_CONSULTATION,
        "treatments": [
            {"slug": t["slug"], "name": t["name"], "blurb": t["blurb"],
             "items": [{"name": n, "desc": d} for n, d in t["items"]]}
            for t in TREATMENTS
        ],
        "physiotherapy": PHYSIO,
    }


def flat_service_names() -> list[str]:
    """All service names — used by pickers for consultations and care logs."""
    out: list[str] = []
    for t in TREATMENTS:
        for n, _ in t["items"]:
            out.append(f"{t['name']} — {n}")
    return out
