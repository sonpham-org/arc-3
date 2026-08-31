"""q514 Moraine Frame -- solve local glacier frames into an outer dependency board."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,CREVASSE,RAFT,FRAME,LOCAL,OUTER,ORDER,GOAL,BAD=0,10,9,14,6,11,12,7,13,15
LEVELS=[
 {"name":"First Enclosure","seq":(1,3)},{"name":"Rotated Ice","seq":(2,1,3)},
 {"name":"Outer Token","seq":(1,3,4,2,1,3)},{"name":"Completion Order","seq":(2,1,3,4,1,2,1,3)},
 {"name":"Nested Moraine","seq":(1,2,1,3,4,2,1,3,4,1,3)},
 {"name":"Moraine Frame","seq":(2,1,3,4,1,2,1,3,4,2,2,1,3)}]
def advance(s,a):
 cell,pos,frame,outer,order,locked=s;outer=list(outer)
 if a==1:pos=(pos+(1 if frame%2==0 else -1))%6
 elif a==2:frame=(frame+1)%4
 elif a==3:outer[cell]=(pos+frame+1)%4;order=order+(cell,)
 elif a==4:cell=(cell+1)%3;pos=(pos+cell)%6
 elif a==5:locked=(cell,pos,frame,tuple(outer),order)
 return cell,pos,frame,tuple(outer),order,locked
for x in LEVELS:
 s=(0,0,0,(0,0,0),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["target"]=s[:-1];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,0,(0,0,0),(),None)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ICE
  for i in range(3):
   x=8+i*18;f[8:31,x:x+14]=CREVASSE;f[11:27,x+3:x+11]=LOCAL if i!=g.cell else FRAME
  px=11+g.cell*18+(g.pos%2)*4;py=12+(g.pos//2)*5;f[py:py+4,px:px+4]=RAFT
  for i,v in enumerate(g.outer):f[38:44,8+i*18:8+i*18+v*3+4]=OUTER
  for i,v in enumerate(g.order[-5:]):f[49:54,8+i*9:14+i*9]=ORDER if v%2 else FRAME
  if g.locked:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q514(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q514",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cell=self.pos=self.frame=0;self.outer=(0,0,0);self.order=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cell,self.pos,self.frame,self.outer,self.order,self.locked=advance((self.cell,self.pos,self.frame,self.outer,self.order,self.locked),a)
  elif a==6:
   if (self.cell,self.pos,self.frame,self.outer,self.order,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
