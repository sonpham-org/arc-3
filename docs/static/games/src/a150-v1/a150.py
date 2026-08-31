"""a150 Intent Trace -- perturb the environment to distinguish goal from route replay."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,WORLD,WALKER,OBSTACLE,GOAL_A,GOAL_B,PATH,REPLAN,HYPOTHESIS,CONSISTENT=1,8,12,6,10,14,9,13,11,4
BAD=15
LEVELS=[
 {"name":"Move Obstacle","seq":(1,)},{"name":"Choose Goal","seq":(2,)},
 {"name":"Run Replan","seq":(3,1)},{"name":"Compare Trajectory","seq":(1,2,3,4,2)},
 {"name":"Infer Intent","seq":(1,3,2,1,4,3,2)},{"name":"Intent Trace","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 obstacle,hypothesis,phase,walker,path,replans,consistent,history,snapshot=s
 if a==1:obstacle=(obstacle+1)%9;history=(history+(1,))[-8:]
 elif a==2:hypothesis=1-hypothesis;history=(history+(2,))[-8:]
 elif a==3:
  phase=(phase+1)%6;goal=8 if hypothesis else 2;step=1 if goal>walker else -1;candidate=(walker+step)%9
  if candidate==obstacle:candidate=(candidate+3)%9;replans=(replans+1)%6
  walker=candidate;path=(path+(walker,))[-7:];history=(history+(3,))[-8:]
 elif a==4:goal=8 if hypothesis else 2;consistent=sum(int(abs(x-goal)<=abs(path[max(0,i-1)]-goal)) for i,x in enumerate(path));history=(history+(4,))[-8:]
 elif a==5:snapshot=(obstacle,hypothesis,phase,walker,path,replans,consistent,history)
 return obstacle,hypothesis,phase,walker,path,replans,consistent,history,snapshot
for q in LEVELS:
 s=(4,0,0,0,(),0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WORLD
  for i in range(9):x=9+(i%3)*16;y=11+(i//3)*15;f[y:y+12,x:x+12]=PATH
  ox=11+(g.obstacle%3)*16;oy=13+(g.obstacle//3)*15;f[oy:oy+8,ox:ox+8]=OBSTACLE;wx=11+(g.walker%3)*16;wy=13+(g.walker//3)*15;f[wy:wy+8,wx:wx+8]=WALKER
  f[12:20,44:52]=GOAL_A;f[42:50,44:52]=GOAL_B;f[7:10,8:8+g.replans*8]=REPLAN;f[54:58,8:8+min(7,g.consistent)*6]=CONSISTENT;f[54:58,51:58]=HYPOTHESIS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A150(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a150",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.obstacle,self.hypothesis,self.phase,self.walker,self.path,self.replans,self.consistent,self.history,self.snapshot=(4,0,0,0,(),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.obstacle,self.hypothesis,self.phase,self.walker,self.path,self.replans,self.consistent,self.history,self.snapshot=advance((self.obstacle,self.hypothesis,self.phase,self.walker,self.path,self.replans,self.consistent,self.history,self.snapshot),a)
  elif a==6:
   if (self.obstacle,self.hypothesis,self.phase,self.walker,self.path,self.replans,self.consistent,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
