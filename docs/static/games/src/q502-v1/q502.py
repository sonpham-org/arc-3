"""q502 Tide Frame -- compose local carrier motion with a moving current before exchange."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CURRENT,SHELL,MOTE,EVIDENCE,FRAME,GATE,BAD=11,9,10,14,15,12,6,0,8
LEVELS=[{"name":"Local Tide","required":2,"plan":(1,5)},{"name":"Translated Basin","required":1,"plan":(2,4,1,5)},{"name":"Rotated Current","required":2,"plan":(3,1,2,5)},{"name":"Edge Exchange","required":2,"plan":(1,4,3,2,5,1)},{"name":"Unsafe Branch","required":3,"plan":(2,3,5,4,1,2,5)},{"name":"Tide Frame","required":6,"plan":(3,1,4,2,5,3,1,5)}]
def advance(s,a):
 motes,rotation,offset,evidence=s;motes=list(motes)
 if a in (1,2):
  i=(a-1+rotation)%3;motes[i]=(motes[i]+(1 if a==1 else -1)+offset)%5
 elif a==3:rotation=(rotation+1)%4;motes=motes[1:]+motes[:1]
 elif a==4:offset=(offset+1)%5;motes=[(v+offset)%5 for v in motes]
 elif a==5:evidence|=1<<((sum(motes)+rotation+offset)%3)
 return tuple(motes),rotation,offset,evidence
def target(x):
 s=((0,2,4),0,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=BASIN
  for i,v in enumerate(g.motes):x=8+i*18;f[10:42,x:x+13]=CURRENT;f[14+v*5:20+v*5,x+3:x+10]=SHELL
  f[44:47,8:8+g.rotation*11]=FRAME;f[49:52,8:8+g.offset*9]=MOTE
  for i in range(3):f[55:59,8+i*15:19+i*15]=EVIDENCE if g.evidence&(1<<i) else GATE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q502(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.motes=(0,2,4);self.rotation=self.offset=self.evidence=0;self.bad=False;self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q502",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.motes=(0,2,4);self.rotation=self.offset=self.evidence=0;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.motes,self.rotation,self.offset,self.evidence=advance((self.motes,self.rotation,self.offset,self.evidence),a)
  elif a==6:
   if (self.motes,self.rotation,self.offset,self.evidence)==self.target and self.evidence&x["required"]==x["required"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
