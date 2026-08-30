"""q407 Spectrum Delegation -- integrate partial prism views after relational transfer."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PRISM,PACKET,CONTROL,MARK,DOMAIN,INTEGRATE,BAD=15,1,12,9,14,6,10,11,8
LEVELS=[{"name":"Split Spectrum","plan":(1,3,4,2,3,5)},{"name":"Remote Pane","plan":(2,3,4,1,3,5)},{"name":"Relation Mark","plan":(1,2,3,4,2,3,5)},{"name":"Geometry Transfer","plan":(2,1,3,4,1,2,3,5)},{"name":"Agent Domain","plan":(1,3,4,2,1,3,5,4,2)},{"name":"Spectrum Delegation","plan":(2,1,3,4,1,3,5,4,2,3,5)}]
def advance(s,a):
 controller,views,marks,domain,integrated=s;views=list(views);marks=list(marks)
 if a in (1,2):views[controller]|=1<<((controller+a+domain+sum(views))%4)
 elif a==3:marks[controller]=(views[controller]*3+domain+controller+1)%8
 elif a==4:controller=1-controller
 elif a==5:domain=1-domain;integrated=(marks[0]^marks[1]^views[domain])%8
 return controller,tuple(views),tuple(marks),domain,integrated
def target(x):
 s=(0,(0,0),(0,0),0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GALLERY;f[9:21,25:39]=PRISM
  for i,v in enumerate(g.views):f[27+i*14:34+i*14,8:8+v*5]=PACKET;f[35+i*14:38+i*14,8:8+max(1,g.marks[i])*5]=MARK
  f[50:53,8:14]=INTEGRATE;f[50:53,16:16+g.integrated*6]=INTEGRATE
  f[54:57,8:14]=CONTROL;f[54:57,16:16+g.controller*22]=CONTROL
  f[58:60,8:14]=DOMAIN;f[58:60,16:16+g.domain*24]=DOMAIN
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q407(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset();ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q407",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.views=(0,0);self.marks=(0,0);self.domain=self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.controller,self.views,self.marks,self.domain,self.integrated=advance((self.controller,self.views,self.marks,self.domain,self.integrated),a)
  elif a==6:
   if (self.controller,self.views,self.marks,self.domain,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
