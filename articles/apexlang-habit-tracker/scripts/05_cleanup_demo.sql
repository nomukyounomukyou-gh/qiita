-- Removes rows for ONE dedicated APEX demo login, not the APEX account.
-- Run as the parsing schema.
-- Preview: @scripts/05_cleanup_demo.sql HABIT_DEMO PREVIEW
-- Delete:  @scripts/05_cleanup_demo.sql HABIT_DEMO DELETE
set define on
set verify off
set serveroutput on
whenever sqlerror exit sql.sqlcode rollback
select habit_name, start_date, archived_date
from ht_habit where owner_name=upper('&1') order by habit_id;
begin
  if upper('&2')<>'DELETE' then
    dbms_output.put_line('Preview only. No rows removed.');
    return;
  end if;
  delete from ht_checkin
  where habit_id in (select habit_id from ht_habit where owner_name=upper('&1'));
  dbms_output.put_line('Removed check-ins: '||sql%rowcount);
  delete from ht_habit where owner_name=upper('&1');
  dbms_output.put_line('Removed habits: '||sql%rowcount);
  commit;
end;
/
