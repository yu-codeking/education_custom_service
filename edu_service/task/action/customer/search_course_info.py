from typing import Any

from edu_service.domain.state import DialogueState
from edu_service.task.action.base import Action, ActionResult
from edu_service.task.action.customer.shared import (
    delivery_mode_name,
    get_series_cohorts,
    get_series_detail,
    search_series,
)


class ActionSearchCourseInfo(Action):
    name = "action_search_course_info"

    async def run(
        self, action_kwargs: dict[str, Any], state: DialogueState
    ) -> ActionResult:
        """
        职责：按课程关键词搜索在售课程，并汇总课程概述与在售班次信息回填槽位
        """

        keyword = str(state.active_task.slots.get("course_keyword") or "").strip()
        rows = await search_series(keyword, state) if keyword else []

        if not rows:
            return ActionResult(
                updated_slots={
                    "series_title": keyword or "该课程",
                    "course_overview": f"暂时没有找到和「{keyword}」相关的在售课程。",
                    "course_cohorts": "",
                }
            )

        best = rows[0]
        detail = await get_series_detail(best.get("seriesId"), state)
        cohorts = await get_series_cohorts(best.get("seriesId"), state)

        series_title = str(
            (detail or {}).get("seriesName") or best.get("seriesName") or keyword
        )

        overview_parts: list[str] = []
        if detail:
            description = str(detail.get("description") or "").strip().replace("\n", "")
            if description:
                overview_parts.append(
                    f"课程简介：{description[:100]}{'…' if len(description) > 100 else ''}"
                )
            mode = delivery_mode_name(detail.get("deliveryModeCode"))
            score = detail.get("avgScore")
            overview_parts.append(
                f"授课方式：{mode}，学员评分 {float(score):.1f} 分"
                if score is not None
                else f"授课方式：{mode}"
            )

        cohort_parts: list[str] = []
        for cohort in cohorts[:3]:
            cohort_parts.append(
                f"{cohort.get('cohortName')}（{delivery_mode_name(best.get('deliveryModeCode'))}，"
                f"¥{cohort.get('salePrice')}，{cohort.get('startDate') or '开课时间待定'} 开班）"
            )

        candidates = ""
        if len(rows) > 1:
            others = "、".join(str(row.get("seriesName")) for row in rows[1:4])
            candidates = f" 另外还找到了：{others}，感兴趣也可以问我。"

        updated_slots = {
            "series_title": series_title,
            "course_overview": "。".join(
                part.strip() for part in overview_parts if part.strip()
            )
            + ("。" if overview_parts else ""),
            "course_cohorts": ("在售班次：" + "；".join(cohort_parts) + "。")
            if cohort_parts
            else "目前没有可报名的班次。",
        }
        updated_slots["course_cohorts"] += candidates
        return ActionResult(updated_slots=updated_slots)
