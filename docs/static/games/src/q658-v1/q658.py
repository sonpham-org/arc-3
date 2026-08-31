"""q658 Breakwater Analogy -- a latent transform wakes after two solved harbor branches."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,CHANNEL,SOURCE,TARGET,LATENT,SUBGOAL,PROOF,BAD=12,8,11,6,2,9,4,13,15
LEVELS=[
 {"name":"Dormant Transform","plan":(1,2,3,3,4,5)},{"name":"Second Transform","plan":(2,2,3,3,4,5)},
 {"name":"Changed Source","plan":(1,1,2,3,3,4,5)},{"name":"Three Branches","plan":(1,2,3,3,3,4,5)},
 {"name":"Latent Relation","plan":(2,1,2,3,3,1,4,5)},{"name":"Breakwater Analogy","plan":(1,2,1,2,3,3,4,1,4,5)}]
def advance(s,a,x):
 source,target_relation,latent,subgoals,visible,proof=s
 if a==1:source=(source+1)%4
 elif a==2:
  if subgoals:return None
  latent=(latent+1)%4
 elif a==3:
  subgoals+=1
  if subgoals>=2:visible=latent
 elif a==4:
  if subgoals<2:return None
  target_relation=(source+visible)%4
 elif a==5:
  if target_relation!=(source+visible)%4:return None
  proof=(source,target_relation,latent,subgoals,visible)
 return source,target_relation,latent,subgoals,visible,proof
def target(x):
 s=(0,0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HARBOR
  for i in range(4):
   f[9+i*9:15+i*9,8:25]=SOURCE if i==g.source else CHANNEL
   f[9+i*9:15+i*9,39:56]=TARGET if i==g.target_relation else CHANNEL+1
  f[47:50,8:8+g.latent*11]=LATENT;f[53:56,8:8+g.subgoals*8]=SUBGOAL
  if g.proof:f[44:58,57:60]=PROOF
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q658(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q658",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=self.target_relation=self.latent=self.subgoals=self.visible=0;self.proof=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.source,self.target_relation,self.latent,self.subgoals,self.visible,self.proof),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.source,self.target_relation,self.latent,self.subgoals,self.visible,self.proof=s
  elif a==6:
   if (self.source,self.target_relation,self.latent,self.subgoals,self.visible,self.proof)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
