"""q347 Spectrum Survey -- budget evidence whose relation transfers across domains."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PANE,PACKET,LENS,EVIDENCE,DOMAIN,POLICY,BAD=4,10,9,14,6,11,5,7,15
LEVELS=[{"name":"One Slice","budget":1,"plan":(1,5)},{"name":"Agent Sample","budget":2,"plan":(2,4,1,5)},{"name":"Relational Union","budget":3,"plan":(1,3,4,2,5)},{"name":"Domain Survey","budget":3,"plan":(2,4,3,1,5)},{"name":"Transfer Evidence","budget":4,"plan":(3,1,4,2,3,5)},{"name":"Spectrum Survey","budget":4,"plan":(1,4,3,2,4,3,5)}]
def advance(s,a):
 domain,evidence,cost,policy=s;evidence=list(evidence)
 if a in (1,2,3):item=(domain,a,(a*2+domain+1)%4);cost+=2 if item in evidence else 1;evidence.append(item)
 elif a==4:domain=1-domain
 elif a==5:policy=(sum(v for *_,v in evidence)+domain)%4
 return domain,tuple(evidence),cost,policy
def target(x):
 s=(0,(),0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for i in range(3):x=8+i*18;f[9:32,x:x+14]=LENS;f[15+i*4:22+i*4,x+4:x+10]=PACKET-i
  for i,(*_,v) in enumerate(g.evidence[-6:]):f[36+i*3:38+i*3,8:11+v*11]=EVIDENCE
  f[53:56,8:11+g.domain*22]=DOMAIN;f[57:60,8:11+g.policy*12]=POLICY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q347(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q347",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.domain=self.cost=self.policy=0;self.evidence=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   self.domain,self.evidence,self.cost,self.policy=advance((self.domain,self.evidence,self.cost,self.policy),a)
   if self.cost>x["budget"]:self.bad=True;self.lose()
  elif a==6:
   if (self.domain,self.evidence,self.cost,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
