-- Read-only comparison with the APEX dashboard.
-- Usage: @scripts/04_check_metrics.sql HABIT_DEMO
set define on
set verify off
set pagesize 100
set linesize 180
with days as (
  select ht_api.today-7+level dt from dual connect by level<=7
)
select to_char(d.dt,'YYYY-MM-DD') checkin_day,
       count(h.habit_id) planned_habits,
       count(c.checkin_id) completed_habits,
       round(count(c.checkin_id)*100/nullif(count(h.habit_id),0),1) completion_pct
from days d
left join ht_habit h
  on h.owner_name=upper('&1')
 and h.start_date<=d.dt
 and (h.archived_date is null or d.dt<h.archived_date)
left join ht_checkin c on c.habit_id=h.habit_id and c.checkin_date=d.dt
group by d.dt
order by d.dt;
