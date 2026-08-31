"""a114 Capacity Match -- meet machine capacities and mixed-skill lower quotas."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FACTORY,MACHINE,WORK_A,WORK_B,ASSIGNED,QUOTA,OVERLOAD,MISSING,BAD=11,8,7,12,14,10,13,6,4,15
SKILLS=(1,2,1,2,3,3)
LEVELS=[
 {"name":"Assign Worker","seq":(1,)},{"name":"Select Worker","seq":(2,)},
 {"name":"Inspect Skill","seq":(3,1)},{"name":"Respect Capacity","seq":(1,2,3,4,2)},
 {"name":"Meet Lower Quota","seq":(1,3,2,1,4,3,2)},{"name":"Capacity Match","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 assignments,cursor,skill_view,loads,coverage,violations,history,snapshot=s;ass=list(assignments)
 if a==1:ass[cursor]=(ass[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:skill_view=(skill_view+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  loads=tuple(ass.count(m) for m in range(3));coverage=tuple(sum(SKILLS[i] for i,x in enumerate(ass) if x==m) for m in range(3));violations=sum(max(0,loads[m]-2)+int(coverage[m]<2) for m in range(3));history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(ass),cursor,skill_view,loads,coverage,violations,history)
 return tuple(ass),cursor,skill_view,loads,coverage,violations,history,snapshot
for x in LEVELS:
 s=((0,0,1,1,2,2),0,0,(2,2,2),(3,3,6),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FACTORY
  for m in range(3):
   x=8+m*17;f[10:27,x:x+14]=MACHINE;f[13:24,x+3:x+11]=QUOTA if g.coverage[m]>=2 else MISSING
  for i,m in enumerate(g.assignments):
   x=9+m*17+(i%2)*6;y=34+(i//2)*7;f[y:y+6,x:x+5]=WORK_A if SKILLS[i]&1 else WORK_B
   if i==g.cursor:f[y-3:y,x-1:x+6]=ASSIGNED
  f[54:58,8:8+g.violations*7]=OVERLOAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A114(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a114",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.assignments,self.cursor,self.skill_view,self.loads,self.coverage,self.violations,self.history,self.snapshot=((0,0,1,1,2,2),0,0,(2,2,2),(3,3,6),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.assignments,self.cursor,self.skill_view,self.loads,self.coverage,self.violations,self.history,self.snapshot=advance((self.assignments,self.cursor,self.skill_view,self.loads,self.coverage,self.violations,self.history,self.snapshot),a)
  elif a==6:
   if (self.assignments,self.cursor,self.skill_view,self.loads,self.coverage,self.violations,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
