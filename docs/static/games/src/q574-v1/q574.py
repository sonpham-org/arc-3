"""q574 Moraine Counter -- shape a rival before solving an outer glacier dependency."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,RAFT,CREVASSE,TACTIC0,TACTIC1,TACTIC2,OUTER,GOAL,BAD=2,10,14,11,6,9,12,7,13,15
LEVELS=[
 {"name":"First Rival","seq":(1,2)},{"name":"Repeated Treatment","seq":(1,1)},
 {"name":"Second Enclosure","seq":(1,3,2)},{"name":"Shaped Moraine","seq":(2,1,2)},
 {"name":"Outer Counter","seq":(1,2,3,2,1)},{"name":"Moraine Counter","seq":(2,1,3,2,2,1,3)}]
def advance(s,a):
 recent,cell,pos,rival,outer,solved,exploited=s;outer=list(outer)
 if a in (1,2):
  p=a-1;recent=(recent+(p,))[-2:];pos=(pos+a+cell)%8;rival=(sum((i+1)*v for i,v in enumerate(recent))+cell+int(len(recent)==2 and recent[0]==recent[1]))%3
 elif a==3:cell=(cell+1)%3;pos=(pos+cell)%8
 elif a==4:outer[cell]=rival+1;solved=solved+(cell,)
 elif a==5:exploited=(rival,tuple(outer),solved,tuple(recent))
 return recent,cell,pos,rival,tuple(outer),solved,exploited
for x in LEVELS:
 s=((),0,0,0,(0,0,0),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(4,5)
def target(x):
 s=((),0,0,0,(0,0,0),(),None)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ICE;f[8:20,8:56]=CREVASSE
  for i in range(8):x=9+i*6;f[12:18,x:x+4]=RAFT if i==g.pos else CREVASSE
  cols=(TACTIC0,TACTIC1,TACTIC2)
  for i,c in enumerate(cols):f[25:38,8+i*18:22+i*18]=c if i==g.rival else OUTER
  for i,v in enumerate(g.outer):f[44:49,8+i*18:8+i*18+v*3+4]=cols[i]
  for i,v in enumerate(g.solved[-4:]):f[52:56,8+i*10:15+i*10]=OUTER if v%2 else CREVASSE
  if g.exploited:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q574(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q574",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.cell=self.pos=self.rival=0;self.outer=(0,0,0);self.solved=();self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.recent,self.cell,self.pos,self.rival,self.outer,self.solved,self.exploited=advance((self.recent,self.cell,self.pos,self.rival,self.outer,self.solved,self.exploited),a)
  elif a==6:
   if (self.recent,self.cell,self.pos,self.rival,self.outer,self.solved,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
