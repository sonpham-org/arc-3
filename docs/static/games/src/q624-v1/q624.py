"""q624 Honeycomb Sandbox -- preserve simulation evidence across nested clock resets."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,LEFT,RIGHT,EVIDENCE,LOCAL,OUTER,BAD=5,8,12,6,2,9,4,13,15
LEVELS=[
 {"name":"First Shared Event","cycle":3,"plan":(1,2,4,5)},{"name":"Four-Step Cycle","cycle":4,"plan":(1,2,4,4,5)},
 {"name":"Evidence Reset","cycle":3,"plan":(1,2,3,4,5)},{"name":"Repeated Simulations","cycle":4,"plan":(1,2,3,1,2,5)},
 {"name":"Nested Clock","cycle":5,"plan":(1,2,3,1,2,4,5)},{"name":"Honeycomb Sandbox","cycle":6,"plan":(1,2,1,3,2,1,4,5)}]
def advance(s,a,x):
 sims,evidence,local,outer,chosen=s;sims=list(sims)
 if a in (1,2):
  i=a-1;sims[i]=(sims[i]+i+2)%7;evidence|=1<<i;local+=1
 elif a==3:sims=[0,0]
 elif a==4:local+=1
 elif a==5:
  if local%x["cycle"] or evidence!=3:return None
  chosen=1 if sims[1]>sims[0] else 0
 wraps=local//x["cycle"]
 if wraps:outer+=wraps;local%=x["cycle"]
 return tuple(sims),evidence,local,outer,chosen
def target(x):
 s=((0,0),0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HIVE;f[8:31,7:29]=CELL;f[8:31,35:57]=CELL+1
  f[26-g.sims[0]*3:28,10:26]=LEFT;f[26-g.sims[1]*3:28,38:54]=RIGHT
  if g.evidence&1:f[35:39,9:25]=EVIDENCE
  if g.evidence&2:f[35:39,39:55]=EVIDENCE
  f[44:48,8:8+g.local*8]=LOCAL;f[51:55,8:8+g.outer*8]=OUTER
  if g.chosen is not None:f[38:58,56:59]=EVIDENCE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q624(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q624",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.evidence=self.local=self.outer=0;self.chosen=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.evidence,self.local,self.outer,self.chosen),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.evidence,self.local,self.outer,self.chosen=s
  elif a==6:
   if (self.sims,self.evidence,self.local,self.outer,self.chosen)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
