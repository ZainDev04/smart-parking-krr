"""The Smart Parking domain written as frames.

This is where knowledge acquisition ends up: each class frame records what
the parking office told us about a kind of thing (its attributes, the
allowed values, the usual default), and each instance frame records one
real individual of the test campus.

The logic layer never re-types these facts. KnowledgeBase facts are
produced from these frames by FrameSystem.to_facts().
"""

from __future__ import annotations

from .frames import Frame, FrameSystem, Slot

TODAY = 20261002          # dates are written as YYYYMMDD integers so they compare as numbers

# Allowed symbolic values. The same names are used in rules, DL and the network.
VEHICLE_TYPES = ("car", "electric_car", "motorbike")
SPACE_TYPES = ("standard", "accessible", "ev_charging", "motorbike")
SPACE_STATUSES = ("vacant", "occupied", "reserved")
PERMIT_CLASSES = ("student_permit", "employee_permit", "visitor_pass")
PERMIT_STATUSES = ("active", "suspended", "revoked")
ZONE_TYPES = ("student_zone", "employee_zone", "visitor_zone")
YES_NO = ("yes", "no")


# ----- if-needed procedures (procedural attachments) ----------------------

def zone_capacity(fs: FrameSystem, frame: Frame) -> int:
    """count of ParkingSpace instances whose locatedIn is this zone"""
    return sum(1 for s in fs.instances("ParkingSpace") if fs.value(s.name, "locatedIn") == frame.name)


def space_zone_type(fs: FrameSystem, frame: Frame):
    """zoneType of the zone this space is located in"""
    if frame.kind != "instance":
        return None
    zone = fs.value(frame.name, "locatedIn")
    return fs.value(zone, "zoneType") if zone else None


def build_frames() -> FrameSystem:
    fs = FrameSystem()

    # ----- people ------------------------------------------------------
    fs.define_class("Person", None, (
        Slot("fullName", "str", doc="display name"),
        Slot("accessibilityBadge", "symbol", default="no", range=YES_NO,
             predicate="accessibility_badge",
             doc="holds a disability parking badge issued by the university"),
        Slot("owns", "frame:Vehicle", cardinality="multiple", predicate="owns",
             relation="owns", doc="vehicles registered to this person"),
        Slot("hasPermit", "frame:ParkingPermit", cardinality="multiple",
             predicate="has_permit", relation="has-a", doc="parking permits or passes held"),
    ), predicate="person", doc="anyone who may drive onto campus")

    fs.define_class("Student", "Person", (
        Slot("studentId", "str"),
        Slot("department", "str"),
    ), predicate="student")

    fs.define_class("Employee", "Person", (
        Slot("employeeId", "str"),
        Slot("department", "str"),
    ), predicate="employee", doc="faculty and staff share employee parking rules")

    fs.define_class("Faculty", "Employee", (
        Slot("designation", "str", default="Lecturer"),
    ), predicate="faculty")

    fs.define_class("Staff", "Employee", (
        Slot("jobTitle", "str"),
    ), predicate="staff")

    fs.define_class("Visitor", "Person", (
        Slot("purpose", "str", default="campus visit"),
        Slot("hostDepartment", "str"),
    ), predicate="visitor")

    # ----- vehicles and permits ----------------------------------------
    fs.define_class("Vehicle", None, (
        Slot("plateNo", "str"),
        Slot("vehicleType", "symbol", default="car", range=VEHICLE_TYPES,
             predicate="vehicle_type", relation="has-type"),
    ), predicate="vehicle")

    fs.define_class("ParkingPermit", None, (
        Slot("permitClass", "symbol", range=PERMIT_CLASSES, predicate="permit_class",
             relation="has-class"),
        Slot("status", "symbol", default="active", range=PERMIT_STATUSES,
             predicate="permit_status"),
        Slot("startDate", "int", predicate="permit_start", doc="YYYYMMDD, first valid day"),
        Slot("expiryDate", "int", predicate="permit_expiry", doc="YYYYMMDD, last valid day"),
    ), predicate="permit", doc="a student or employee permit, or a one-day visitor pass")

    # ----- places --------------------------------------------------------
    fs.define_class("ParkingFacility", None, (
        Slot("campus", "str", default="NED University main campus"),
    ), predicate="parking_facility")

    fs.define_class("ParkingZone", None, (
        Slot("zoneType", "symbol", range=ZONE_TYPES, predicate="zone_type", relation="has-type"),
        Slot("openHour", "int", default=7, predicate="zone_opens"),
        Slot("closeHour", "int", default=22, predicate="zone_closes"),
        Slot("partOf", "frame:ParkingFacility", predicate="part_of", relation="part-of"),
        Slot("capacity", "int", if_needed=zone_capacity),
    ), predicate="parking_zone")

    fs.define_class("ParkingSpace", None, (
        Slot("locatedIn", "frame:ParkingZone", predicate="located_in", relation="part-of"),
        Slot("spaceType", "symbol", default="standard", range=SPACE_TYPES,
             predicate="space_type", relation="has-type"),
        Slot("status", "symbol", default="vacant", range=SPACE_STATUSES,
             predicate="space_status"),
        Slot("zoneType", "symbol", if_needed=space_zone_type),
    ), predicate="parking_space")

    fs.define_class("AccessibleSpace", "ParkingSpace", (
        Slot("spaceType", default="accessible"),
        Slot("widthMetres", "str", default="3.6"),
    ), doc="wider bay near the entrance, reserved for badge holders")

    fs.define_class("EVChargingSpace", "ParkingSpace", (
        Slot("spaceType", default="ev_charging"),
        Slot("chargerKW", "int", default=7),
    ))

    fs.define_class("MotorbikeSpace", "ParkingSpace", (
        Slot("spaceType", default="motorbike"),
    ))

    fs.define_class("Reservation", None, (
        Slot("madeBy", "frame:Person", predicate="reserved_by", relation="made-by"),
        Slot("forSpace", "frame:ParkingSpace", predicate="reserved_space", relation="for-space"),
        Slot("date", "int", predicate="reservation_date", doc="YYYYMMDD"),
    ), predicate="reservation")

    _add_instances(fs)
    return fs


def _add_instances(fs: FrameSystem) -> None:
    # People. Student and employee ids are invented for the test campus.
    fs.define_instance("ali", "Student", fullName="Ali Raza", studentId="CS-22-101",
                       department="CSIT", owns=["car_ali"], hasPermit=["p_ali"])
    fs.define_instance("sara", "Student", fullName="Sara Khan", studentId="CS-22-114",
                       department="CSIT", accessibilityBadge="yes",
                       owns=["car_sara"], hasPermit=["p_sara"])
    fs.define_instance("usman", "Student", fullName="Usman Ghani", studentId="EE-21-087",
                       department="Electrical", owns=["car_usman"], hasPermit=["p_usman"])
    fs.define_instance("zara", "Student", fullName="Zara Ahmed", studentId="CS-23-045",
                       department="CSIT", owns=["car_zara"], hasPermit=["p_zara"])
    fs.define_instance("ahmed", "Faculty", fullName="Dr. Ahmed Siddiqui", employeeId="F-0192",
                       department="CSIT", designation="Assistant Professor",
                       owns=["ev_ahmed"], hasPermit=["p_ahmed"])
    fs.define_instance("fatima", "Staff", fullName="Fatima Noor", employeeId="S-0441",
                       department="CSIT", jobTitle="Lab Engineer",
                       owns=["bike_fatima"], hasPermit=["p_fatima"])
    fs.define_instance("bilal", "Visitor", fullName="Bilal Hussain", purpose="guest lecture",
                       hostDepartment="CSIT", owns=["car_bilal"], hasPermit=["vp_bilal"])
    fs.define_instance("hina", "Visitor", fullName="Hina Shah", purpose="admission enquiry",
                       owns=["car_hina"])

    # Vehicles. vehicleType is left to the default (car) unless it differs.
    for vid, plate in (("car_ali", "BKR-101"), ("car_sara", "BKS-202"),
                       ("car_usman", "AKU-303"), ("car_zara", "BLZ-404"),
                       ("car_bilal", "AXB-505"), ("car_hina", "BHH-606")):
        fs.define_instance(vid, "Vehicle", plateNo=plate)
    fs.define_instance("ev_ahmed", "Vehicle", plateNo="EV-707", vehicleType="electric_car")
    fs.define_instance("bike_fatima", "Vehicle", plateNo="KMB-808", vehicleType="motorbike")

    # Permits. A permit is valid from startDate to expiryDate inclusive; status
    # defaults to active. p_usman expired on 15 Sep 2026. vp_bilal starts and
    # ends on the same day, so it is a one-day pass.
    fs.define_instance("p_ali", "ParkingPermit", permitClass="student_permit",
                       startDate=20260701, expiryDate=20270630)
    fs.define_instance("p_sara", "ParkingPermit", permitClass="student_permit",
                       startDate=20260701, expiryDate=20270630)
    fs.define_instance("p_usman", "ParkingPermit", permitClass="student_permit",
                       startDate=20250916, expiryDate=20260915)
    fs.define_instance("p_zara", "ParkingPermit", permitClass="student_permit",
                       startDate=20260701, expiryDate=20270630)
    fs.define_instance("p_ahmed", "ParkingPermit", permitClass="employee_permit",
                       startDate=20260101, expiryDate=20271231)
    fs.define_instance("p_fatima", "ParkingPermit", permitClass="employee_permit",
                       startDate=20260101, expiryDate=20271231)
    fs.define_instance("vp_bilal", "ParkingPermit", permitClass="visitor_pass",
                       startDate=TODAY, expiryDate=TODAY,
                       doc="one-day pass issued by the CSIT office")

    # Facility and zones.
    fs.define_instance("ned_lot", "ParkingFacility")
    fs.define_instance("zone_a", "ParkingZone", zoneType="student_zone", partOf="ned_lot")
    fs.define_instance("zone_e", "ParkingZone", zoneType="employee_zone", partOf="ned_lot",
                       openHour=6, closeHour=23)
    fs.define_instance("zone_v", "ParkingZone", zoneType="visitor_zone", partOf="ned_lot",
                       openHour=8, closeHour=17)

    # Spaces. spaceType and status come from defaults unless stated.
    fs.define_instance("s_a1", "ParkingSpace", locatedIn="zone_a")
    fs.define_instance("s_a2", "ParkingSpace", locatedIn="zone_a", status="occupied")
    fs.define_instance("s_a3", "AccessibleSpace", locatedIn="zone_a")
    fs.define_instance("s_a4", "MotorbikeSpace", locatedIn="zone_a")
    fs.define_instance("s_a5", "ParkingSpace", locatedIn="zone_a", status="reserved")
    fs.define_instance("s_e1", "ParkingSpace", locatedIn="zone_e")
    fs.define_instance("s_e2", "EVChargingSpace", locatedIn="zone_e")
    fs.define_instance("s_e3", "ParkingSpace", locatedIn="zone_e", status="reserved")
    fs.define_instance("s_v1", "ParkingSpace", locatedIn="zone_v")

    # Reservations for today.
    fs.define_instance("r1", "Reservation", madeBy="zara", forSpace="s_a5", date=TODAY)
    fs.define_instance("r2", "Reservation", madeBy="ahmed", forSpace="s_e3", date=TODAY)
