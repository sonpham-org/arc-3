"""q644 Tessera Sandbox -- preserve mosaic evidence while folded simulations reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,TESS0,TESS1,TESS2,SEAM,EVIDENCE,RESET,GOAL,BAD=4,10,11,14,12,6,7,9,13,15
LEVELS=[
 {"name":"Twin Mosaics","seq":(1,2)},{"name":"Repeated Tile","seq":(1,1,2)},
 {"name":"Folded Copies","seq":(1,3,2)},{"name":"Persistent Tessera","seq":(1,2,4,2,1)},
 {"name":"Topology Evidence","seq":(2,3,1,1,4,2,1)},
 {"name":"Tessera Sandbox","seq":(1,3,2,2,4,2,3,1,1)}]
def advance(s,a):
 sims,fold,evidence,committed=s;sims=list(sims)
 if a in (1,2):
  i=a-1;reading=(i+fold+sims[i])%3;sims[i]+=1;evidence=evidence+((i,reading),)
 elif a==3:sims.reverse();fold=(fold+1)%3
 elif a==4:sims=[0,0];fold=0
 elif a==5:
  if {i for i,_ in evidence}!={0,1}:return None
  committed=(tuple(sims),fold,len(evidence),sum(v for _,v in evidence)%4)
 return tuple(sims),fold,evidence,committed
for x in LEVELS:
 s=((0,0),0,(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=((0,0),0,(),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;cols=(TESS0,TESS1,TESS2)
  for i in range(2):
   x=8+i*27;f[8:33,x:x+21]=RESET
   for row in range(3):
    for col in range(3):f[11+row*7:16+row*7,x+2+col*6:x+7+col*6]=cols[(row+col+g.fold+i)%3]
   f[35:39,x:x+min(g.sims[i],5)*4]=SEAM
  for j,(i,v) in enumerate(g.evidence[-6:]):f[45:50,8+j*8:14+j*8]=EVIDENCE if i else cols[v]
  f[53:57,8:8+g.fold*15+10]=SEAM
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q644(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q644",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.fold=0;self.evidence=();self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.fold,self.evidence,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.fold,self.evidence,self.committed=s
  elif a==6:
   if (self.sims,self.fold,self.evidence,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
