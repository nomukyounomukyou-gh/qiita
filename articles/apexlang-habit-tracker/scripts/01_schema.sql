set define off
whenever sqlerror exit sql.sqlcode rollback
create table ht_habit (
  habit_id number generated always as identity primary key,
  owner_name varchar2(255 char) not null,
  habit_name varchar2(80 char) not null,
  description varchar2(500 char),
  color_code varchar2(20 char) default 'green' not null,
  icon_name varchar2(40 char) default 'fa-check-circle' not null,
  start_date date default trunc(cast(systimestamp at time zone 'Asia/Tokyo' as date)) not null,
  archived_date date,
  display_order number default 10 not null,
  created_at timestamp with time zone default systimestamp not null,
  updated_at timestamp with time zone default systimestamp not null,
  constraint ht_habit_name_ck check(trim(habit_name) is not null),
  constraint ht_habit_color_ck check(color_code in ('green','blue','orange','purple')),
  constraint ht_habit_icon_ck check(icon_name in ('fa-check-circle','fa-book','fa-heart','fa-bicycle')),
  constraint ht_habit_dates_ck check(start_date=trunc(start_date) and (archived_date is null or (archived_date=trunc(archived_date) and archived_date>=start_date)))
);
create index ht_habit_owner_ix on ht_habit(owner_name);
create table ht_checkin (
  checkin_id number generated always as identity primary key,
  habit_id number not null references ht_habit(habit_id),
  checkin_date date not null,
  note varchar2(500 char),
  created_at timestamp with time zone default systimestamp not null,
  constraint ht_checkin_day_uk unique(habit_id,checkin_date),
  constraint ht_checkin_day_ck check(checkin_date=trunc(checkin_date))
);
create or replace package ht_api authid definer as
  function today return date;
  function owner_name return varchar2;
  procedure save_habit(p_id in out number,p_name varchar2,p_description varchar2,p_color varchar2,p_icon varchar2,p_order number);
  procedure record_today(p_id number,p_note varchar2);
  procedure undo_today(p_id number);
  procedure archive_habit(p_id number);
end ht_api;
/
create or replace package body ht_api as
  function today return date is
  begin return trunc(cast(systimestamp at time zone 'Asia/Tokyo' as date)); end;
  function owner_name return varchar2 is
    l_user varchar2(255):=upper(v('APP_USER'));
  begin
    if l_user is null or l_user in ('NOBODY','APEX_PUBLIC_USER') then
      raise_application_error(-20001,'ログインしてください。');
    end if;
    return l_user;
  end;
  procedure assert_owned(p_id number,p_active boolean default false) is
    l_id number;
    l_owner varchar2(255):=owner_name;
  begin
    select habit_id into l_id from ht_habit
     where habit_id=p_id and ht_habit.owner_name=l_owner
       and (not p_active or (archived_date is null and start_date<=ht_api.today)) for update;
  exception when no_data_found then raise_application_error(-20002,'対象の習慣を操作できません。');
  end;
  procedure save_habit(p_id in out number,p_name varchar2,p_description varchar2,p_color varchar2,p_icon varchar2,p_order number) is
    l_owner varchar2(255):=owner_name;
  begin
    if trim(p_name) is null then raise_application_error(-20003,'習慣名を入力してください。'); end if;
    if p_id is null then
      insert into ht_habit(owner_name,habit_name,description,color_code,icon_name,display_order)
      values(l_owner,trim(p_name),p_description,p_color,p_icon,nvl(p_order,10)) returning habit_id into p_id;
    else
      assert_owned(p_id,true);
      update ht_habit set habit_name=trim(p_name),description=p_description,color_code=p_color,
       icon_name=p_icon,display_order=nvl(p_order,10),updated_at=systimestamp where habit_id=p_id;
    end if;
  end;
  procedure record_today(p_id number,p_note varchar2) is
  begin
    assert_owned(p_id,true);
    merge into ht_checkin c using(select p_id id,ht_api.today dt from dual) s
    on(c.habit_id=s.id and c.checkin_date=s.dt)
    when matched then update set c.note=p_note
    when not matched then insert(habit_id,checkin_date,note) values(s.id,s.dt,p_note);
  end;
  procedure undo_today(p_id number) is
  begin
    assert_owned(p_id,true);
    delete from ht_checkin where habit_id=p_id and checkin_date=ht_api.today;
  end;
  procedure archive_habit(p_id number) is
  begin
    assert_owned(p_id,true);
    update ht_habit set archived_date=ht_api.today,updated_at=systimestamp where habit_id=p_id;
  end;
end ht_api;
/
show errors
