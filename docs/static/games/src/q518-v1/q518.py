"""q518 Asterism Frame -- compose local motion with a precessing orbital chart."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,STAR,LINK,MOVER,PHASE,MEMORY,GOAL,BAD=0,9,11,10,14,6,12,13,15
LEVELS=[
 {"name":"Local Orbit","seq":(1,1)},{"name":"Precessed Step","seq":(2,1,1)},
 {"name":"Chart Memory","seq":(1,3,2,1)},{"name":"Reset Observatory","seq":(2,1,3,4,1,1)},
 {"name":"Nested Bearings","seq":(1,2,1,3,2,1,4,2,1)},
 {"name":"Asterism Frame","seq":(2,1,3,2,1,1,4,2,2,1,3,1)}]
def advance(s,a):
 pos,phase,evidence,locked=s
 if a==1:pos=(pos+(1 if phase<2 else -1))%8
 elif a==2:phase=(phase+1)%4
 elif a==3:evidence=evidence+((pos+2*phase)%5,)
 elif a==4:pos=phase=0
 elif a==5:locked=(pos,phase,evidence)
 return pos,phase,evidence,locked
for x in LEVELS:
 s=(0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["target"]=(s[0],s[1],s[2]);x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,(),None)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  pts=[(13,30),(18,18),(30,13),(42,18),(47,30),(42,42),(30,47),(18,42)]
  for i,(y,x) in enumerate(pts):f[y-2:y+3,x-2:x+3]=MOVER if i==g.pos else STAR
  for i in range(4):f[30+i%2,12+i*10:22+i*10]=LINK
  f[52:56,8:8+g.phase*11]=PHASE
  for i,v in enumerate(g.evidence[-5:]):f[7:11,8+i*9:14+i*9]=MEMORY if v%2 else GOAL
  if g.locked:f[56:60,40:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q518(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q518",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=self.phase=0;self.evidence=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.phase,self.evidence,self.locked=advance((self.pos,self.phase,self.evidence,self.locked),a)
  elif a==6:
   if (self.pos,self.phase,self.evidence,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
