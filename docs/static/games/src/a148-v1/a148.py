"""a148 Reactive Floor -- identify a stateless response field through counterfactual starts."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FLOOR,PLAYER,FIELD_A,FIELD_B,START,ROUTE,REPLAY,FIXED,GOAL_LIKE=15,8,12,10,14,13,9,11,4,6
BAD=7
LEVELS=[
 {"name":"Change Start","seq":(1,)},{"name":"Advance Route","seq":(2,)},
 {"name":"Replay Path","seq":(3,1)},{"name":"Compare Counterfactual","seq":(1,2,3,4,2)},
 {"name":"Infer Reactive Rule","seq":(1,3,2,1,4,3,2)},{"name":"Reactive Floor","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 start,step,replay,response,fixed_score,goal_score,history,snapshot=s
 if a==1:start=(start+1)%6;history=(history+(1,))[-8:]
 elif a==2:step=(step+1)%8;history=(history+(2,))[-8:]
 elif a==3:replay=1-replay;history=(history+(3,))[-8:]
 elif a==4:response=tuple((start+i*2+step)%9 for i in range(4));fixed_score=sum(int(x%3==(start+step)%3) for x in response);goal_score=sum(int(abs(x-4)<2) for x in response);history=(history+(4,))[-8:]
 elif a==5:snapshot=(start,step,replay,response,fixed_score,goal_score,history)
 return start,step,replay,response,fixed_score,goal_score,history,snapshot
for q in LEVELS:
 s=(0,0,0,(),0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FLOOR
  for i in range(9):x=10+(i%3)*16;y=11+(i//3)*15;f[y:y+12,x:x+12]=FIELD_A if (i+g.route_step)%2==0 else FIELD_B
  px=13+(g.start%3)*16;py=14+(g.start//3)*15;f[py:py+7,px:px+7]=PLAYER;f[7:10,8:8+g.route_step*5]=ROUTE;f[54:58,8:28]=REPLAY if g.replay else START;f[54:58,31:31+g.fixed_score*6]=FIXED;f[54:58,50:50+g.goal_score*2]=GOAL_LIKE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A148(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a148",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.start,self.route_step,self.replay,self.response,self.fixed_score,self.goal_score,self.history,self.snapshot=(0,0,0,(),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.start,self.route_step,self.replay,self.response,self.fixed_score,self.goal_score,self.history,self.snapshot=advance((self.start,self.route_step,self.replay,self.response,self.fixed_score,self.goal_score,self.history,self.snapshot),a)
  elif a==6:
   if (self.start,self.route_step,self.replay,self.response,self.fixed_score,self.goal_score,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
