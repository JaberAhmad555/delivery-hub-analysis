// Editable native charts/tables. Usage: node build_presentation.mjs PROJECT BUILD SKILL PYTHON
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation, PresentationFile} from '@oai/artifact-tool';
const [root,build,skill,python]=process.argv.slice(2);
if(!python)throw new Error('Provide PROJECT BUILD SKILL PYTHON absolute paths');
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')));
const f=JSON.parse(await fs.readFile(path.join(root,'outputs/final/verified_facts.json'),'utf8'));
await fs.mkdir(build,{recursive:true}); await fs.mkdir(path.join(build,'renders'),{recursive:true}); await fs.mkdir(path.join(build,'final'),{recursive:true});
const deck=Presentation.create({slideSize:{width:1280,height:720}});
deck.theme.defaultFont='Arial';
const ink='#143638', teal='#087F79', amber='#E5A449',muted='#657F83', light='#F4F7F6';
const money=n=>'BDT '+n.toLocaleString('en-US',{maximumFractionDigits:2});
function text(s,str,x,y,w,h,size=24,color=ink,bold=false){const a=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});a.text=str;a.text.style={typeface:'Arial',fontSize:size,color,bold};return a;}
function slide(title,sub,source){const s=deck.slides.add();s.background.fill=light;text(s,'CARRYBEE  /  OPERATIONS INTELLIGENCE',54,28,1120,28,14,teal,true);text(s,title,54,72,1170,70,38,ink,true);text(s,sub,54,147,1170,54,20,muted);text(s,`MANAGEMENT REVIEW DRAFT   |   ${deck.slides.items.length} / 8`,54,670,1150,26,13,muted);s.speakerNotes.text=`Source: ${source}. Historical period 13-26 October 2026. Projection 27 October-23 November 2026. All projected benefits are assumptions, not observed effects. Financial values are BDT.`;return s;}
function table(s,rows,x,y,width,height,widths,size=20){const t=s.tables.add({rows:rows.length,columns:rows[0].length,left:x,top:y,width,height,columnWidths:widths,values:rows});for(let r=0;r<rows.length;r++)for(let c=0;c<rows[0].length;c++){const a=t.getCell(r,c);a.fill=r===0?teal:(r%2?'#FFFFFF':'#E8F0EE');a.text.style={typeface:'Arial',fontSize:size,color:r===0?'#FFFFFF':ink,bold:r===0};}t.borders.assign({fill:'#D6E3E0',width:1,style:'solid'});return t;}
const charts=[];
function chart(s,type,categories,series,x,y,w,h,percent=false){series=series.map(a=>({...a,values:a.values.map(v=>Number(v.toFixed(6)))}));const cfg={position:{left:x,top:y,width:w,height:h},categories,series,hasLegend:series.length>1,legend:{position:'bottom',overlay:false,textStyle:{fontSize:16}},chartFill:light,plotAreaFill:light,barOptions:{direction:'column',grouping:'clustered'},xAxis:{textStyle:{fontSize:17}},yAxis:{min:0,numberFormatCode:percent?'0%':'#,##0',textStyle:{fontSize:17},majorGridlines:{fill:'#D6E3E0',width:1}},dataLabels:{showValue:series.length===1,position:'outEnd',numberFormatCode:percent?'0.0%':'#,##0',textStyle:{fontSize:16}}};const c=s.charts.add(type,cfg);applyPresentationChartFont(c,{fontFamily:'Arial'});charts.push({slide:deck.slides.items.length,categories,series:series.map(a=>({name:a.name,values:a.values}))});return c;}
let s=slide('Approve targeted capacity, not eight hires','Decision for the next 28 operating days', 'scenario_comparison.csv; budget_allocation.csv; q8_hub_decisions.csv');
text(s,'BDT 65,400',54,229,590,90,58,teal,true);text(s,'committed reserve  |  BDT 4,600 retained',54,325,620,42,24);
text(s,'2 transfers  +  2 hires',54,414,620,54,35,ink,true);text(s,'Lakeview → Greenfield\nTwo fixed-salary hires at Hillcrest\nHold programme at Riverside',54,483,650,126,25);
text(s,'82.6%',820,234,370,80,58,teal,true);text(s,'less 85%-target queue exposure',820,325,390,68,23);text(s,'Service investment',820,434,390,44,30,ink,true);text(s,'First-month package cash ROI: -73.79%. No guaranteed revenue uplift.',820,493,375,110,23);
s.speakerNotes.text+=' Queue exposure falls from 50,791.6363 to 8,843.5375 attempt-days. It is a modelled planning metric, not observed backlog or lost deliveries.';
s=slide('Workload rose faster than staffing','Week 1 versus Week 2 | observed attempt outcomes', 'dashboard_data/historical_hub_week.csv');
chart(s,'bar',['Assigned','Delivered','Hold','Returned'],f.history.map((a,i)=>({name:'Week '+a.week,values:[a.attempts,a.delivered,a.holds,a.returned],fill:i?teal:'#A6C8C1'})),54,225,790,380);
text(s,'+19.0%',900,233,320,80,54,teal,true);text(s,'assigned attempts',900,313,300,42,24);text(s,'BDT 37.32 → 33.78',900,421,320,56,27,ink,true);text(s,'cost per delivered order\n\nMore throughput spreads paid staffing cost.',900,490,310,132,22);
s=slide('Three hubs crossed the 85% target','Week 2 utilisation = Assigned attempts / (eligible agent-days × 40)', 'outputs/q2_utilisation.csv');
chart(s,'bar',f.hubs.map(a=>a.hub),[{name:'Week 2 utilisation',values:f.hubs.map(a=>a.historical_util),fill:teal}],54,215,1150,330,true);
text(s,'85% planning benchmark',54,558,540,35,23,teal,true);text(s,'Lakeview: 56.17% → eligible donor. Two transfers leave nine agents versus a peak need of eight.',54,606,1150,50,22);
s=slide('Riverside holds are the actionable pressure','Week 2 | hold events, with customer and agent causes separated', 'outputs/q3_hold_reasons.csv; outputs/q5_high_return_agents.csv');
chart(s,'bar',f.hubs.map(a=>a.hub),[{name:'Agent-side',values:f.hold_reasons.map(a=>a.agent_side_holds),fill:amber},{name:'Customer-side',values:f.hold_reasons.map(a=>a.total_holds-a.agent_side_holds),fill:'#A6C8C1'}],54,225,800,363);
text(s,'563 / 874',900,229,320,68,43,teal,true);text(s,'Riverside agent-side holds\n64.42% of its Week 2 holds',900,310,318,77,23);text(s,'Brookside return review',900,433,315,57,25,ink,true);text(s,'Three established agents exceed 15%: 26.93%, 21.98%, 17.43%. Investigate before action.',900,504,315,118,22);
s=slide('Four-week pressure improves, with an early gap','Peak hub utilisation by forecast week | target remains 85%', 'weekly_staffing_plan.csv; q7_staffing_forecast.csv');
chart(s,'line',['W1','W2','W3','W4'],[{name:'Baseline',values:f.weekly.map(a=>a.baseline_max_util),line:{fill:amber,width:3},fill:amber},{name:'Recommended',values:f.weekly.map(a=>a.after_max_util),line:{fill:teal,width:3},fill:teal},{name:'85% target',values:[.85,.85,.85,.85],line:{fill:muted,width:2},fill:muted}],54,228,650,330,true);
table(s,[['Hub','Now','Peak need','Plan'],...f.hubs.map(a=>[a.hub,a.current,a.peak_required,a.roster])],755,227,470,335,[185,80,112,93],19);
text(s,'Hillcrest hires: 60% productivity in Week 1. Riverside benefit starts on day 15. Base-case 100%-standard queue ends at zero in every forecast week under the plan.',54,593,1150,65,21);
s=slide('The eight-hire request does not fit the budget','Compare affordable service alternatives before committing', 'scenario_comparison.csv; scenario_manifest.json');
const names=['Transfers only','Riverside programme only','Transfer + Riverside programme','Transfer + two Hillcrest hires','Recommended - robust 28-day budget','Eight fixed hires'];
const selected=names.map(n=>f.scenarios.find(a=>a.scenario===n));
table(s,[['Strategy','Reserve BDT','End 85% queue','Queue attempt-days'],...selected.map((a,i)=>[['Transfers','Riverside programme','Transfers + programme','Transfers + 2 hires','Recommended combination','Eight fixed hires'][i],a.budget_reserved_bdt.toLocaleString('en-US'),a.end_planning_backlog.toFixed(1),Math.round(a.planning_backlog_attempt_days).toLocaleString('en-US')])],54,225,1150,325,[450,200,230,270],22);
text(s,'BDT 185,600 for eight hires; BDT 115,600 above the ceiling.',54,570,1150,39,27,teal,true);text(s,'Recommended plan minimises planning-queue exposure among 2,864 feasible fixed-pay, day-1 plans. It is a service objective, not profit maximisation.',54,617,1150,42,19);
s=slide('Spend BDT 65,400; retain BDT 4,600','Base case: 28 paid days and no programme benefit during days 1–14', 'budget_allocation.csv; scenario_comparison.csv; sensitivity_analysis.csv');
table(s,[['Allocation','BDT'],['Two transfers','4,000'],['Recruit two fixed agents','10,000'],['New payroll: 2 × 28 × 650','36,400'],['Riverside hold programme','15,000'],['Intervention total','65,400'],['Unallocated balance','4,600']],54,225,635,340,[440,195],23);
text(s,money(f.recommended.direct_hold_cost_savings_bdt),755,228,465,64,38,teal,true);text(s,'projected hold-charge savings\n571.36 holds prevented; 530.96 retries avoided inside 28 days.',755,302,460,116,23);
text(s,'Net cash cost: BDT 48,259.35',755,433,460,45,26,ink,true);text(s,'26-day same plan: BDT 62,800.\nLinear ramp savings: BDT 25,076.09.\nNo extra revenue or retry cash saving.',755,492,460,112,22);
text(s,'Programme-only ROI 14.27%; extrapolated payback 26.3 days. These exclude staffing and transfer costs and are not whole-plan returns.',54,612,1150,48,19);
s=slide('Control the first 14 days before expanding spend','Daily control tower review; formal checkpoints on days 3, 7, 10 and 14', 'risk_register.csv; sensitivity_analysis.csv');
table(s,[['Risk','Early warning / action trigger','Accountable team'],['Demand / capacity','>10% demand for 3 days; >100% load any day','Planning + Hub Ops'],['New-hire learning','<60% in week 1; <40% for 2 days','Hub Manager + Training'],['Hold programme','<90% checklist by day 7; <90% trained by day 14','Riverside + Process'],['Customer holds / returns','>20% relative increase for 3 days; ≥100 attempts','Customer Support + Quality'],['Transfer disruption','Donor >85%; transfer productivity <80% for 2 days','HR + Cluster A'],['Budget overrun','Reserve <BDT 2,000; total >BDT 70,000 prohibited','Finance + HR']],54,222,1150,348,[262,598,290],20);
text(s,'Downside: +20% demand leaves 709.75 attempts above the standard-capacity queue by day 28. Reforecast promptly; release contingency only against a refreshed 28-day budget.',54,593,1150,64,22);
await fs.writeFile(path.join(build,'chart_data_contract.json'),JSON.stringify(charts,null,2));
for(const [i,s] of deck.slides.items.entries()){const png=await deck.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(build,'renders',`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));}
// The PDF companion is assembled from these genuine slide renders by build_slide_pdf.py.
const candidate=path.join(build,'candidate.pptx');await(await PresentationFile.exportPptx(deck)).save(candidate);
const result=await finalizePresentation({workspaceDir:build,candidatePath:candidate,finalPath:path.join(build,'final','CarryBee_Management_Presentation.pptx'),pythonExecutable:python,integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...[5,6,7,8].flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:8,requiredNativeTableOwnerSlides:[5,6,7,8],requiredNativeChartOwnerSlides:[2,3,4,5],tableArithmeticContracts:[{slide:7,table:1,label_column:0,total_row:5,value_columns:[1],component_rows:[1,2,3,4]}],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,receiptPath:path.join(build,'presentation-validation.json')});
console.log(JSON.stringify(result));



