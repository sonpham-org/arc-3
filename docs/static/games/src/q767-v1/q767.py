"""q767 Spectrum Obligation -- repay identity-bound photon debt after packets exchange bands."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GALLERY,PRISM,PACKET,IDENTITY,BAND,DEBT,GOAL,BAD=8,0,12,14,6,10,9,13,15
LEVELS=[
 {"name":"Borrowed Ray","seq":(4,)},{"name":"Moved Creditor","seq":(4,1)},
 {"name":"Split Identity","seq":(4,2,1)},{"name":"Delayed Repayment","seq":(4,1,3,2)},
 {"name":"Packet Exchange","seq":(4,2,1,3,2,1)},
 {"name":"Spectrum Obligation","seq":(4,1,2,3,1,2,3,1,2)}]
def advance(s,a):
 identities,bands,creditor,debt,discharged=s;i=list(identities);b=list(bands)
 if a==1:i[0],i[1]=i[1],i[0];b[0],b[1]=b[1],b[0]
 elif a==2:i=i[1:]+i[:1];b=b[-1:]+b[:-1]
 elif a==3:b=[(v+j+1)%6 for j,v in enumerate(b)]
 elif a==4:creditor=i[1];debt=(b[1]+2)%6
 elif a==5:discharged=(i.index(creditor),debt,tuple(b),tuple(i)) if creditor>=0 else None
 return tuple(i),tuple(b),creditor,debt,discharged
for x in LEVELS:
 s=((0,1,2,3),(0,2,4,1),-1,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for slot,(identity,band) in enumerate(zip(g.identities,g.bands)):
   x=7+slot*14;f[9:31,x:x+10]=PRISM;f[13+band*2:19+band*2,x+2:x+8]=PACKET
   f[33+identity:36+identity,x:x+10]=IDENTITY
  if g.creditor>=0:
   x=7+g.identities.index(g.creditor)*14;f[41:46,x:x+10]=DEBT
  f[49:53,8:8+g.debt*8+5]=BAND
  if g.discharged:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q767(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q767",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2,3);self.bands=(0,2,4,1);self.creditor=-1;self.debt=0;self.discharged=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.bands,self.creditor,self.debt,self.discharged=advance((self.identities,self.bands,self.creditor,self.debt,self.discharged),a)
  elif a==6:
   if (self.identities,self.bands,self.creditor,self.debt,self.discharged)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
