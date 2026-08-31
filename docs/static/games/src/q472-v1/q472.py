"""q472 Tide Dependency -- reuse shell prerequisites before one irreversible commitment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CURRENT,SHELL,SHARED,BRANCH,EVIDENCE,COMMIT,BAD=9,10,12,14,5,11,6,7,15
LEVELS=[{"name":"One Prerequisite","branches":1,"coverage":1,"plan":(1,4,5)},{"name":"Shared Shell","branches":1,"coverage":2,"plan":(2,1,4,5)},{"name":"Two Branches","branches":2,"coverage":3,"plan":(1,2,4,3,4,5)},{"name":"Reversing Current","branches":2,"coverage":3,"plan":(3,1,2,4,2,1,4,5)},{"name":"Delayed Seal","branches":3,"coverage":3,"plan":(1,3,4,2,4,1,2,3,4,5)},{"name":"Tide Dependency","branches":3,"coverage":3,"plan":(3,1,2,4,1,3,4,2,1,4,5)}]
def advance(s,a,x):
 shells,current,evidence,shared,branches,irreversible=s;shells=list(shells);evidence=list(evidence);branches=list(branches)
 if a in (1,2,3):i=a-1;shells[i]+=1;evidence.append((a,current,tuple(shells)))
 elif a==4:
  if not sum(shells):return None
  shared=(sum((i+1)*v for i,v in enumerate(shells))+current+len(branches))%8;branches.append((shared,current));shells=[0,0,0];current=1-current
 elif a==5:
  if len(branches)<x["branches"] or len({e[0] for e in evidence})<x["coverage"]:return None
  irreversible=(shared,tuple(branches),tuple(evidence),current)
 return tuple(shells),current,tuple(evidence),shared,tuple(branches),irreversible
def target(x):
 s=((0,0,0),0,(),0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN;f[8:31,7:57]=CURRENT
  for i,v in enumerate(g.shells):x=10+i*17;f[25-v*4:28,x:x+11]=SHELL-i
  for i,(v,_) in enumerate(g.branches[-6:]):f[36+i*3:38+i*3,8:11+v*6]=BRANCH
  f[48:51,8:24]=EVIDENCE;f[53:56,8:11+g.shared*6]=SHARED;f[56:59,44:56]=COMMIT if g.irreversible else BASIN
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q472(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q472",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.shells=(0,0,0);self.current=0;self.evidence=();self.shared=0;self.branches=();self.irreversible=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.shells,self.current,self.evidence,self.shared,self.branches,self.irreversible),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.shells,self.current,self.evidence,self.shared,self.branches,self.irreversible=s
  elif a==6:
   if (self.shells,self.current,self.evidence,self.shared,self.branches,self.irreversible)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
