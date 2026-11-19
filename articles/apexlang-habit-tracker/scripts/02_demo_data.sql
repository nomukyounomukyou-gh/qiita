-- Optional synthetic data for screenshots and chart exploration.
-- Run only in the demo schema, after creating the End User in APEX.
-- Usage: @scripts/02_demo_data.sql HABIT_DEMO
-- The argument is the APEX login name, not the database user name.
set define on
set verify off
set serveroutput on
whenever sqlerror exit sql.sqlcode rollback
declare
  l_owner varchar2(255):=upper('&1');
  l_id number;
  l_count number;
  l_today date:=trunc(cast(systimestamp at time zone 'Asia/Tokyo' as date));
begin
  select count(*) into l_count from ht_habit
  where owner_name=l_owner and habit_name in ('読書を20分','朝のウォーキング','ストレッチ');
  if l_count>0 then
    raise_application_error(-20010,'Demo habits already exist. No data was changed.');
  end if;
  for h in 1..3 loop
    insert into ht_habit(owner_name,habit_name,description,color_code,icon_name,start_date,display_order)
    values(l_owner,
      case h when 1 then '読書を20分' when 2 then '朝のウォーキング' else 'ストレッチ' end,
      case h when 1 then '朝の静かな時間に、気になる本を少しずつ。'
             when 2 then '外の空気を吸って、一日のリズムを整える。'
             else '眠る前の5分間。肩と背中をゆっくり伸ばす。' end,
      case h when 1 then 'green' when 2 then 'blue' else 'orange' end,
      case h when 1 then 'fa-book' when 2 then 'fa-bicycle' else 'fa-heart' end,
      l_today-13,h*10)
    returning habit_id into l_id;
    for d in 0..13 loop
      if (h=1 and d not in (3,6,10)) or (h=2 and mod(d,2)=0) or (h=3 and mod(d,3)<>0) then
        insert into ht_checkin(habit_id,checkin_date,note)
        values(l_id,l_today-d,'記事用の架空サンプル記録');
      end if;
    end loop;
  end loop;
  commit;
  dbms_output.put_line('Synthetic demo data created for the specified APEX login.');
end;
/
