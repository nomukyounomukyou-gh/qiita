-- Run as the application's parsing schema in a test environment.
-- Usage: @scripts/03_verify.sql 110
-- Creates no persistent test data: all test rows are rolled back.
set serveroutput on
set define on
set verify off
whenever sqlerror exit sql.sqlcode rollback
declare
  l_id number;
  l_count number;
  procedure expect(p_condition boolean,p_message varchar2) is
  begin
    if not p_condition or p_condition is null then
      raise_application_error(-20100,p_message);
    end if;
    dbms_output.put_line('PASS: '||p_message);
  end;
begin
  apex_session.create_session(p_app_id=>&1,p_page_id=>1,p_username=>'HT_VERIFY_A');
  savepoint habit_verify;
  expect(ht_api.today=trunc(cast(systimestamp at time zone 'Asia/Tokyo' as date)),'JST date');
  ht_api.save_habit(l_id,'Verification habit',null,'green','fa-book',10);
  select count(*) into l_count from ht_habit where habit_id=l_id and owner_name='HT_VERIFY_A';
  expect(l_count=1,'Owner derived from APEX session');
  ht_api.record_today(l_id,'first');
  ht_api.record_today(l_id,'second');
  select count(*) into l_count from ht_checkin where habit_id=l_id;
  expect(l_count=1,'Repeated check-in is idempotent');
  begin
    insert into ht_checkin(habit_id,checkin_date) values(l_id,ht_api.today);
    raise_application_error(-20101,'Duplicate unexpectedly accepted');
  exception when dup_val_on_index then dbms_output.put_line('PASS: Unique constraint'); end;
  apex_application.g_user:='HT_VERIFY_B';
  begin
    ht_api.record_today(l_id,null);
    raise_application_error(-20102,'Cross-user update unexpectedly accepted');
  exception when others then
    if sqlcode<>-20002 then raise; end if;
    dbms_output.put_line('PASS: Cross-user update rejected');
  end;
  apex_application.g_user:='HT_VERIFY_A';
  ht_api.undo_today(l_id);
  ht_api.undo_today(l_id);
  select count(*) into l_count from ht_checkin where habit_id=l_id;
  expect(l_count=0,'Repeated undo is idempotent');
  ht_api.record_today(l_id,'kept after archive');
  ht_api.archive_habit(l_id);
  select count(*) into l_count from ht_checkin where habit_id=l_id;
  expect(l_count=1,'Archive retains history');
  begin
    ht_api.record_today(l_id,null);
    raise_application_error(-20103,'Archived check-in unexpectedly accepted');
  exception when others then
    if sqlcode<>-20002 then raise; end if;
    dbms_output.put_line('PASS: Archived habit cannot be checked in');
  end;
  rollback to habit_verify;
  dbms_output.put_line('ALL API CHECKS PASSED; test rows rolled back');
exception when others then rollback; raise;
end;
/
