"""q569 Strata Counter -- shape a rival while reversible probes leave knowledge behind."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,FAULT,ORE,RIVAL,PROBE,KNOWLEDGE,CLAIM,BAD=15,8,11,6,2,4,9,13,14
LEVELS=[
 {"name":"One Treatment","need":0,"plan":(1,5)},{"name":"Shape Once","need":1,"plan":(1,2,5)},
 {"name":"Undo the Probe","need":1,"plan":(1,4,2,5)},{"name":"Knowledge Remains","need":2,"plan":(1,2,4,3,5)},
 {"name":"Reversible Pressure","need":3,"plan":(1,2,4,3,1,5)},{"name":"Strata Counter","need":4,"plan":(1,4,2,3,4,1,2,5)}]
def advance(s,a,x):
 history,rival,world,knowledge,score,shaped,claimed=s;history=list(history)
 if a in (1,2,3):
  t=a-1
  if history and history[-1]!=t:shaped+=1
  history=(history+[t])[-3:];world=(world+t+1)%4;knowledge|=1<<world;score+=int(t==(rival+1)%3);rival=(sum(history)+knowledge.bit_count())%3
 elif a==4:world=0
 elif a==5:
  if shaped<x["need"]:return None
  claimed=(tuple(history),rival,knowledge,score,shaped)
 return tuple(history),rival,world,knowledge,score,shaped,claimed
def target(x):
 s=((),0,0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=QUARRY
  for i in range(3):x=8+i*17;f[8:36,x:x+13]=FAULT+i
  for i,t in enumerate(g.history):f[28-i*6:33-i*6,10+t*17:19+t*17]=ORE+t
  f[41:45,8:12+g.rival*13]=RIVAL;f[48:51,8:8+g.world*11]=PROBE;f[53:56,8:8+g.knowledge.bit_count()*10]=KNOWLEDGE
  if g.claimed:f[39:58,56:59]=CLAIM
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q569(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q569",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.history=();self.rival=self.world=self.knowledge=self.score=self.shaped=0;self.claimed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.history,self.rival,self.world,self.knowledge,self.score,self.shaped,self.claimed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.history,self.rival,self.world,self.knowledge,self.score,self.shaped,self.claimed=s
  elif a==6:
   if (self.history,self.rival,self.world,self.knowledge,self.score,self.shaped,self.claimed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
