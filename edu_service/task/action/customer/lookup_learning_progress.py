from typing import Any

from edu_service.domain.state import DialogueState
from edu_service.task.action.base import Action, ActionResult
from edu_service.task.action.customer.shared import (
    delivery_mode_name,
    find_cohort_by_name,
    get_my_progress,
    get_series_detail,
)


def _fmt(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _build_progress_summary(cohort_name: str, progress: dict[str, Any]) -> str:
    attendance = progress.get("attendance") or {}
    video = progress.get("video") or {}
    homework = progress.get("homework") or {}
    exam = progress.get("exam") or {}

    lines = [f"你在「{cohort_name}」的学习情况如下："]

    total_sessions = _fmt(attendance.get("totalSessions"))
    present_count = _fmt(attendance.get("presentCount"))
    absent_count = _fmt(attendance.get("absentCount"))
    if total_sessions:
        lines.append(f"· 出勤：到课 {present_count} 次 / 缺勤 {absent_count} 次（共排课 {total_sessions} 次）")
    else:
        lines.append("· 出勤：还没有考勤记录")

    total_videos = _fmt(video.get("totalVideos"))
    completed_videos = _fmt(video.get("completedVideos"))
    watched_seconds = _fmt(video.get("watchedSeconds"))
    if total_videos:
        watched_minutes = max(watched_seconds // 60, 1)
        lines.append(f"· 视频：完成 {completed_videos}/{total_videos} 个（累计观看约 {watched_minutes} 分钟）")

    total_homeworks = _fmt(homework.get("totalHomeworks"))
    submitted_count = _fmt(homework.get("submittedCount"))
    corrected_count = _fmt(homework.get("correctedCount"))
    if total_homeworks:
        expired = _fmt(homework.get("expiredUnsubmittedCount"))
        homework_line = f"· 作业：提交 {submitted_count}/{total_homeworks}，已批改 {corrected_count}"
        if expired:
            homework_line += f"，逾期未交 {expired}"
        lines.append(homework_line)

    total_exams = _fmt(exam.get("totalExams"))
    exam_submitted = _fmt(exam.get("submittedCount"))
    exam_absent = _fmt(exam.get("absentCount"))
    if total_exams:
        exam_line = f"· 考试：参加并通过提交 {exam_submitted}/{total_exams}"
        if exam_absent:
            exam_line += f"，缺考 {exam_absent}"
        lines.append(exam_line)

    return "\n".join(lines)


class ActionLookupLearningProgress(Action):
    name = "action_lookup_learning_progress"

    async def run(self, action_kwargs: dict[str, Any], state: DialogueState) -> ActionResult:
        """
        职责：按班次名称查询学习进度（考勤 / 视频观看 / 作业提交 / 考试参加）
        """
        cohort_name = str(state.active_task.slots.get("cohort_name") or "").strip()

        matched, my_cohorts = await find_cohort_by_name(cohort_name, state)
        if matched is None:
            candidate_names = "、".join(str(c.get("cohortName")) for c in my_cohorts[:3])
            hint = f"我这里有你的这些班次：{candidate_names}。" if candidate_names else ""
            return ActionResult(updated_slots={
                "progress_summary": f"没找到「{cohort_name}」的报名记录。{hint}确认一下想查询的班次吧～",
                "matched_cohort_name": "",
            })

        cohort_id = matched.get("cohortId")
        display_name = str(matched.get("cohortName") or cohort_name)
        progress = await get_my_progress(cohort_id, state)
        if progress is None:
            return ActionResult(updated_slots={
                "progress_summary": f"「{display_name}」的学习数据暂时拉取不到，稍后再试试哦。",
                "matched_cohort_name": display_name,
            })

        enroll_status_code = str(progress.get("enrollStatusCode") or matched.get("enrollStatusCode") or "")
        summary = _build_progress_summary(display_name, progress)
        if enroll_status_code == "completed":
            summary += "\n这个班次你已经结业啦，可以看看其他课程继续提升～"

        return ActionResult(updated_slots={
            "progress_summary": summary,
            "matched_cohort_name": display_name,
        })
