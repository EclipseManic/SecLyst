import pytest

from seclyst_backend.jobs.states import ALLOWED_TRANSITIONS, InvalidTransition, JobStatus, require_transition


def test_every_documented_transition_is_accepted() -> None:
    for current, targets in ALLOWED_TRANSITIONS.items():
        for target in targets:
            assert require_transition(current, target) == (current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.QUEUED, JobStatus.COMPLETED),
        (JobStatus.RUNNING, JobStatus.QUEUED),
        (JobStatus.COMPLETED, JobStatus.QUEUED),
        (JobStatus.CANCELLED, JobStatus.RUNNING),
    ],
)
def test_invalid_transitions_are_rejected(current: JobStatus, target: JobStatus) -> None:
    with pytest.raises(InvalidTransition):
        require_transition(current, target)
