"""q630 Spore Sandbox -- commit only when unequal autonomous clocks share an event."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,GLASS,SPORE,CLOCK,EVIDENCE,RESET,COMMIT,BAD=11,8,12,6,2,9,4,13,15
LEVELS=[
 {"name":"Twin Cycles","cycles":(2,2)},{"name":"Unequal Pair","cycles":(2,3)},{"name":"Triple Pair","cycles":(3,3)},
 {"name":"Sparse Shared Event","cycles":(3,4)},{"name":"Long Alignment","cycles":(4,5)},{"name":"Spore Sandbox","cycles":(5,6)}]
for x in LEVELS:x["plan"]=(1,)*x["cycles"][0]+(2,)*x["cycles"][1]+(3,5)
def advance(s,a,x):
 sims,evidence,clocks,main,chosen=s;sims=list(sims);clocks=list(clocks)
 if a in (1,2):
  i=a-1;sims[i]=(sims[i]+i+2)%7;clocks[i]=(clocks[i]+1)%x["cycles"][i];evidence|=1<<i
 elif a==3:sims=[0,0]
 elif a==4:clocks=[(clocks[i]+1)%x["cycles"][i] for i in range(2)]
 elif a==5:
  if tuple(clocks)!=(0,0) or evidence!=3:return None
  chosen=1 if sims[1]>sims[0] else 0;main=sims[chosen]
 return tuple(sims),evidence,tuple(clocks),main,chosen
def target(x):
 s=((0,0),0,(0,0),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GREENHOUSE;f[8:31,7:29]=GLASS;f[8:31,35:57]=GLASS
  f[26-g.sims[0]*3:28,10:26]=SPORE;f[26-g.sims[1]*3:28,38:54]=SPORE+2
  f[36:40,8:8+g.clocks[0]*9]=CLOCK;f[42:46,8:8+g.clocks[1]*7]=CLOCK+2
  if g.evidence:f[49:52,8:8+g.evidence*12]=EVIDENCE
  f[54:57,8:28]=RESET
  if g.chosen is not None:f[38:58,56:59]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q630(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q630",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.evidence=0;self.clocks=(0,0);self.main=0;self.chosen=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.evidence,self.clocks,self.main,self.chosen),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.evidence,self.clocks,self.main,self.chosen=s
  elif a==6:
   if (self.sims,self.evidence,self.clocks,self.main,self.chosen)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
