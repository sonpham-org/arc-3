"""q344 Tessera Survey -- collect seam evidence before interrupting a compressed fold."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,SEAM,TESSERA,EVIDENCE,PHASE,ROUTE,LATCH,BAD=9,15,7,11,10,12,14,0,8
LEVELS=[
 {"name":"One Slice","required":1,"window":1,"period":4,"plan":(1,4,5)},
 {"name":"Second Seam","required":3,"window":2,"period":5,"plan":(1,2,4,4,5)},
 {"name":"Evidence Union","required":7,"window":3,"period":6,"plan":(1,3,2,4,4,4,5)},
 {"name":"Compressed Fold","required":5,"window":2,"period":5,"plan":(1,3,4,4,5,4)},
 {"name":"Interruption Cost","required":6,"window":4,"period":7,"plan":(2,3,4,4,4,4,5)},
 {"name":"Tessera Survey","required":7,"window":5,"period":8,"plan":(3,1,2,4,4,4,4,4,5,4)}]
def advance(s,a,x):
 evidence,phase,route,latched=s
 if a in (1,2,3):evidence|=1<<(a-1);route=(route+a+evidence)%5
 elif a==4:phase=(phase+1)%x["period"];route=(route+phase+1)%5
 elif a==5:
  if phase!=x["window"] or evidence&x["required"]!=x["required"]:return None
  latched=True;route=(route+bin(evidence).count("1"))%5
 return evidence,phase,route,latched
def target(x):
 s=(0,0,0,False)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MOSAIC
  for i,col in enumerate((TESSERA,EVIDENCE,SEAM)):
   x=8+i*18;f[9:15,x:x+13]=col
   if g.evidence&(1<<i):f[18:36,x:x+13]=col
  f[42:46,7:7+g.phase*6]=PHASE;f[48:52,7:7+g.route*11]=ROUTE
  if g.latched:f[55:59,12:52]=LATCH
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q344(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.evidence=self.phase=self.route=0;self.latched=False;self.bad=False;self.target=target(LEVELS[0])
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q344",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.evidence=self.phase=self.route=0;self.latched=False;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.phase,self.route,self.latched),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.evidence,self.phase,self.route,self.latched=s
  elif a==6:
   if (self.evidence,self.phase,self.route,self.latched)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
