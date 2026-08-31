"""q696 Backstage Evidence -- stop only when signed sightline pressure cannot reverse."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,SAMPLE1,SAMPLE2,SAMPLE3,POSITIVE,NEGATIVE,STOP,BAD=5,13,10,14,6,11,9,12,15
LEVELS=[
 {"name":"Certain Cue","budget":1,"turn":9,"seq":(3,)},{"name":"Negative Pair","budget":3,"turn":9,"seq":(2,2)},
 {"name":"Turning Evidence","budget":4,"turn":2,"seq":(3,3,1)},{"name":"Signed Margin","budget":5,"turn":2,"seq":(2,2,3,3)},
 {"name":"Safe Threshold","budget":6,"turn":3,"seq":(3,3,3,2)},{"name":"Backstage Evidence","budget":8,"turn":3,"seq":(2,2,2,3,3)}]
def scored(x):
 score=0;direction=1
 for i,a in enumerate(x["seq"],1):score+=direction*{1:1,2:-2,3:3}[a];direction=-direction if i==x["turn"] else direction
 return score,direction
for x in LEVELS:
 score,direction=scored(x);assert score and abs(score)>3*(x["budget"]-len(x["seq"]));x["choice"]=0 if score>0 else 1;x["plan"]=x["seq"]+(4+x["choice"],)
def advance(s,a,x):
 score,direction,used,committed=s
 if a in (1,2,3):
  if used>=x["budget"]:return None
  score+=direction*{1:1,2:-2,3:3}[a];used+=1
  if used==x["turn"]:direction*=-1
 elif a in (4,5):
  choice=a-4;remaining=x["budget"]-used
  if not score or abs(score)<=3*remaining or choice!=(0 if score>0 else 1):return None
  committed=(choice,score,direction)
 return score,direction,used,committed
def target(x):
 s=(0,1,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE
  for i,c in enumerate((SAMPLE1,SAMPLE2,SAMPLE3)):f[8:29,8+i*17:22+i*17]=c
  width=min(abs(g.score),12)*3;f[36:41,8:8+width]=POSITIVE if g.score>=0 else NEGATIVE;f[46:50,8:28]=POSITIVE if g.direction>0 else NEGATIVE
  if g.committed:f[54:59,39:56]=STOP
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q696(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q696",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.score=0;self.direction=1;self.used=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.score,self.direction,self.used,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.score,self.direction,self.used,self.committed=s
  elif a==6:
   if (self.score,self.direction,self.used,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
