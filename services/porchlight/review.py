"""Owner-supplied labels are separate from inference, evidence and alert decisions."""

from porchlight.api.contracts import OwnerEntity


def labels_summary(entities: list[OwnerEntity]) -> str:
    if not entities:
        return "No objects labelled by the owner."
    descriptions = []
    for entity in entities:
        label: str = entity.subtype or entity.category
        if entity.color:
            label = f"{entity.color} {label}"
        actions = ", ".join(action.replace("_", " ") for action in entity.actions)
        direction = entity.direction.replace("_", " ")
        descriptions.append(f"{label}: {actions}; {direction}")
    return ". ".join(descriptions) + "."
