"""q623 Ember Sandbox -- evidence survives disposable simulations before one commitment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,SANDBOX,LEFT,RIGHT,EVIDENCE,MAIN,COMMIT,RESOURCE,BAD=13,8,0,6,2,11,4,9,10,15
LEVELS=[
 {"name":"Test Left","rules":(2,1),"plan":(1,4),"budget":4},{"name":"Test Right","rules":(1,3),"plan":(2,4),"budget":4},
 {"name":"Compare Copies","rules":(2,3),"plan":(1,2,4),"budget":5},{"name":"Persistent Evidence","rules":(3,2),"plan":(1,2,3,2,4),"budget":7},
 {"name":"Reset Then Commit","rules":(2,4),"plan":(1,1,2,3,1,2,4,5),"budget":10},
 {"name":"Ember Sandbox","rules":(4,3),"plan":(2,1,2,3,1,1,2,4,5,5),"budget":12}]
def advance(s,a,x):
 sims,evidence,main,chosen,resource=s;sims=list(sims)
 if resource<=0:return None
 resource-=1
 if a==1:sims[0]=(sims[0]+x["rules"][0])%7;evidence|=1
 elif a==2:sims[1]=(sims[1]+x["rules"][1])%7;evidence|=2
 elif a==3:sims=[0,0]
 elif a==4:
  if chosen is not None or not evidence:return None
  chosen=1 if evidence==2 or (evidence==3 and sims[1]>sims[0]) else 0;main=sims[chosen]
 elif a==5:
  if chosen is None:return None
  main=(main+x["rules"][chosen])%7
 return tuple(sims),evidence,main,chosen,resource
def target(x):
 s=((0,0),0,0,None,x["budget"])
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN;f[8:34,7:29]=SANDBOX;f[8:34,35:57]=SANDBOX
  f[29-g.sims[0]*3:31,10:26]=LEFT;f[29-g.sims[1]*3:31,38:54]=RIGHT
  if g.evidence&1:f[36:40,9:25]=EVIDENCE
  if g.evidence&2:f[36:40,39:55]=EVIDENCE
  f[45:51,8:12+g.main*6]=MAIN;f[54:58,8:8+g.resource*4]=RESOURCE
  if g.chosen is not None:f[42:59,56:59]=COMMIT
  if g.bad:f[0:3,17:47]=BAD
  return f
class Q623(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q623",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.evidence=self.main=0;self.chosen=None;self.resource=self.cfg["budget"]
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.evidence,self.main,self.chosen,self.resource),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.evidence,self.main,self.chosen,self.resource=s
  elif a==6:
   if (self.sims,self.evidence,self.main,self.chosen,self.resource)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
