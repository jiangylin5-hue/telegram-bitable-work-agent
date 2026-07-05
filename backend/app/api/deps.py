from app.services.permissions import Actor


def get_system_actor() -> Actor:
    return Actor(actor_type="system", actor_id="stage-02-system", role="admin")
