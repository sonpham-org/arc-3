"""q699 Reedbed Evidence -- build unequal sensors until no remaining result can reverse the choice."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,SENSOR1,SENSOR2,SENSOR3,LINK,SCORE,STOP,BAD=6,10,9,12,14,11,8,13,15
LEVELS=[
 {"name":"Certain Sensor","budget":1,"seq":(3,)},{"name":"Negative Pair","budget":3,"seq":(2,2)},
 {"name":"Safe Network","budget":4,"seq":(3,3,1)},{"name":"Rewired Evidence","budget":5,"seq":(2,2,3,3,3)},
 {"name":"Wide Margin","budget":6,"seq":(3,3,3,2)},{"name":"Reedbed Evidence","budget":8,"seq":(2,2,2,2,2)}]
def scored(seq):return sum({1:1,2:-2,3:3}[a] for a in seq)
for x in LEVELS:
 score=scored(x["seq"]);assert score and abs(score)>3*(x["budget"]-len(x["seq"]));x["choice"]=0 if score>0 else 1;x["plan"]=x["seq"]+(4+x["choice"],)
def advance(s,a,x):
 score,used,links,committed=s
 if a in (1,2,3):
  if used>=x["budget"]:return None
  score+={1:1,2:-2,3:3}[a];links^=1<<(used%6);used+=1
 elif a in (4,5):
  choice=a-4;remaining=x["budget"]-used
  if not score or abs(score)<=3*remaining or choice!=(0 if score>0 else 1):return None
  committed=(choice,links)
 return score,used,links,committed
def target(x):
 s=(0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i,c in enumerate((SENSOR1,SENSOR2,SENSOR3)):f[8:29,8+i*17:22+i*17]=c
  for i in range(6):f[34+i*3:36+i*3,8:28]=LINK if g.links&(1<<i) else WATER
  width=min(abs(g.score),12)*3;f[39:44,36:36+width]=SCORE+(g.score<0)
  if g.committed:f[54:59,39:56]=STOP
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q699(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q699",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.score=self.used=self.links=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.score,self.used,self.links,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.score,self.used,self.links,self.committed=s
  elif a==6:
   if (self.score,self.used,self.links,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
