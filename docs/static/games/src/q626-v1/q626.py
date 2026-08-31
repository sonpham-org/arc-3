"""q626 Palimpsest Sandbox -- preserve the causal distinction after simulations reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,LEFT,RIGHT,FAIL,EVIDENCE,MAIN,BAD=1,8,11,6,2,15,9,4,13
LEVELS=[
 {"name":"Successful Left","bad":1,"rules":(2,1),"both":False,"plan":(1,4)},
 {"name":"Successful Right","bad":0,"rules":(1,3),"both":False,"plan":(2,4)},
 {"name":"Compare Failure","bad":1,"rules":(2,3),"both":True,"plan":(1,2,4)},
 {"name":"Reset the Near Miss","bad":0,"rules":(3,2),"both":True,"plan":(1,3,2,4)},
 {"name":"Persistent Distinction","bad":1,"rules":(2,4),"both":True,"plan":(2,3,1,4,5)},
 {"name":"Palimpsest Sandbox","bad":0,"rules":(4,3),"both":True,"plan":(1,2,3,2,1,4,5,5)}]
def advance(s,a,x):
 sims,evidence,fail,main,chosen=s;sims=list(sims)
 if a in (1,2):
  i=a-1;sims[i]=(sims[i]+x["rules"][i])%7;evidence|=1<<i
  if i==x["bad"]:fail=(i,sims[i])
 elif a==3:sims=[0,0]
 elif a==4:
  if chosen is not None or (x["both"] and evidence!=3) or not (evidence&(1<<(1-x["bad"]))):return None
  chosen=1-x["bad"];main=sims[chosen]
 elif a==5:
  if chosen is None:return None
  main=(main+x["rules"][chosen])%7
 return tuple(sims),evidence,fail,main,chosen
def target(x):
 s=((0,0),0,None,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE;f[8:31,7:29]=SHELF;f[8:31,35:57]=SHELF
  f[27-g.sims[0]*3:29,10:26]=LEFT;f[27-g.sims[1]*3:29,38:54]=RIGHT
  if g.evidence&1:f[36:40,9:25]=EVIDENCE
  if g.evidence&2:f[36:40,39:55]=EVIDENCE
  if g.fail:f[43:47,9+g.fail[0]*30:25+g.fail[0]*30]=FAIL
  f[52:56,8:12+g.main*6]=MAIN
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q626(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q626",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.evidence=0;self.fail=None;self.main=0;self.chosen=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.evidence,self.fail,self.main,self.chosen),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.evidence,self.fail,self.main,self.chosen=s
  elif a==6:
   if (self.sims,self.evidence,self.fail,self.main,self.chosen)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
