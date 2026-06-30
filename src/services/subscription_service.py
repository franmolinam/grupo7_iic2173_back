import boto3
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from src.models.subscription import Subscription, SubscriptionPackage
from src.models.package import Package


def create_subscription(db: Session, user_id: str, data: dict) -> Subscription:
    sub_id = str(uuid.uuid4())
    budget = float(data["budget"])

    sub = Subscription(
        id=sub_id,
        user_id=user_id,
        destination_id=data["destination_id"].upper(),
        height=data["height"],
        width=data["width"],
        depth=data["depth"],
        criteria=data["criteria"],
        max_hops=data["max_hops"],
        deliver_not_before=data.get("deliver_not_before"),
        meta_content=data.get("meta_content", ""),
        periodicity_seconds=data["periodicity_seconds"],
        budget=budget,
        cost_per_shipment=float(data["cost_per_shipment"]),
        quantity=data["quantity"],
        packages_sent=0,
        budget_remaining=budget,
        status="active",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    # Iniciar ejecucion de las step functions
    state_machine_arn = os.getenv("SUBSCRIPTION_STATE_MACHINE_ARN")
    if not state_machine_arn:
        print("[!] SUBSCRIPTION_STATE_MACHINE_ARN no configurado; suscripcion creada sin ejecución SF.")
        sub.status = "failed"
        db.commit()
        db.refresh(sub)
        return sub

    try:
        sfn = boto3.client("stepfunctions", region_name=os.getenv("AWS_REGION", "us-east-2"))
        execution_name = f"sub-{sub_id[:8]}-{int(datetime.now(timezone.utc).timestamp())}"
        response = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps({"subscription_id": sub_id}),
        )
        sub.execution_arn = response["executionArn"]
        db.commit()
        print(f"[*] Step Functions ejecucion iniciada: {sub.execution_arn}")
    except Exception as e:
        print(f"[!] Error al iniciar Step Functions: {e}")
        sub.status = "failed"
        db.commit()

    db.refresh(sub)
    return sub


def get_user_subscriptions(db: Session, user_id: str) -> list:
    return (
        db.query(Subscription)
        .filter_by(user_id=user_id)
        .order_by(Subscription.created_at.desc())
        .all()
    )


def get_subscription_detail(db: Session, subscription_id: str, user_id: str) -> Optional[Subscription]:
    return (
        db.query(Subscription)
        .filter_by(id=subscription_id, user_id=user_id)
        .first()
    )


def get_subscription_packages(db: Session, subscription_id: str) -> list:
    sub_pkgs = (
        db.query(SubscriptionPackage)
        .filter_by(subscription_id=subscription_id)
        .order_by(SubscriptionPackage.created_at.desc())
        .all()
    )

    result = []
    for sp in sub_pkgs:
        pkg = db.query(Package).filter_by(id=sp.package_id).first() if sp.package_id else None
        result.append({
            "subscription_package_id": sp.id,
            "package_id": sp.package_id,
            "status": sp.status,
            "sent_at": sp.created_at,
            "package": {
                "id": pkg.id,
                "destination_id": pkg.destination_id,
                "status": pkg.status,
                "last_action": pkg.last_action,
                "created_at": pkg.created_at,
            } if pkg else None,
        })
    return result
