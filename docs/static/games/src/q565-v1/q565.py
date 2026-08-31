"""q565 Alloy Counter -- shape a rival whose tactics are expressed in a moving frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,BILLET,RIVAL,FRAME,SHAPE,CLAIM,BAD=5,8,11,6,2,9,13,4,15
LEVELS=[
 {"name":"Visible Counter","need":0,"plan":(1,5)},{"name":"Shape Once","need":1,"plan":(1,2,5)},
 {"name":"Rotated Reply","need":1,"plan":(4,1,2,5)},{"name":"Three Tactics","need":2,"plan":(1,4,2,3,5)},
 {"name":"Translated Rival","need":3,"plan":(1,2,4,3,1,5)},{"name":"Alloy Counter","need":4,"plan":(4,1,2,4,3,1,4,2,5)}]
def advance(s,a,x):
 history,rival,origin,rotation,score,shaped,claimed=s;history=list(history)
 if a in (1,2,3):
  local=a-1;t=(local+rotation)%3;old=rival
  if history and history[-1]!=t:shaped+=1
  history=(history+[t])[-3:];score+=int(t==(old+1)%3);rival=(sum(history)+origin+len(history))%3
 elif a==4:origin=(origin+1)%5;rotation=(rotation+1)%3
 elif a==5:
  if shaped<x["need"]:return None
  claimed=(tuple(history),rival,origin,rotation,score,shaped)
 return tuple(history),rival,origin,rotation,score,shaped,claimed
def target(x):
 s=((),0,0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY
  for i in range(3):x=8+i*17;f[8:38,x:x+13]=LANE+i
  for i,t in enumerate(g.history):x=10+((t-g.rotation)%3)*17;f[29-i*6:34-i*6,x:x+9]=BILLET+i
  f[41:45,8:12+g.rival*13]=RIVAL;f[48:51,8:8+g.origin*9]=FRAME;f[53:56,8:8+g.rotation*14]=SHAPE
  if g.claimed:f[39:58,56:59]=CLAIM
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q565(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q565",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.history=();self.rival=self.origin=self.rotation=self.score=self.shaped=0;self.claimed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.history,self.rival,self.origin,self.rotation,self.score,self.shaped,self.claimed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.history,self.rival,self.origin,self.rotation,self.score,self.shaped,self.claimed=s
  elif a==6:
   if (self.history,self.rival,self.origin,self.rotation,self.score,self.shaped,self.claimed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
