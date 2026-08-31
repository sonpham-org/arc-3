"""a047 Two-Phase Move -- reserve destinations before committing every move."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FLOOR,CELL,TILE_A,TILE_B,TILE_C,RESERVE,COMMIT,ARROW,BAD=7,9,8,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Prepare One","seq":(2,)},{"name":"Commit One","seq":(2,4)},
 {"name":"Select Tile","seq":(1,2,4)},{"name":"Avoid Conflict","seq":(2,1,2,3,4)},
 {"name":"Exchange Pair","seq":(2,1,2,3,4,1,2)},{"name":"Two Phase Move","seq":(1,2,3,1,2,4,3,2,4)},
]
def advance(s,a):
 pos,selected,reservations,phase,history,snapshot=s;p=list(pos);r=list(reservations)
 if a==1:selected=(selected+1)%3;history=(history+(1,))[-8:]
 elif a==2:r[selected]=(p[selected]+1+phase+selected)%6;history=(history+(2,))[-8:]
 elif a==3:phase^=1;history=(history+(3,))[-8:]
 elif a==4:
  counts={x:r.count(x) for x in r if x>=0}
  for i,x in enumerate(r):
   if x>=0 and counts[x]==1:p[i]=x
  r=[-1,-1,-1];phase^=1;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),selected,tuple(r),phase,history)
 return tuple(p),selected,tuple(r),phase,history,snapshot
for x in LEVELS:
 s=((0,2,4),0,(-1,-1,-1),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FLOOR
  for i in range(6):x=7+i*9;f[25:40,x:x+8]=CELL
  colors=(TILE_A,TILE_B,TILE_C)
  for i,p in enumerate(g.pos):
   x=8+p*9;f[27:38,x:x+6]=colors[i]
   if i==g.selected:f[20:24,x:x+6]=ARROW
  for i,r in enumerate(g.reservations):
   if r>=0:x=8+r*9;f[42+i*4:45+i*4,x:x+6]=RESERVE
  f[9:15,10:28]=RESERVE if g.phase==0 else COMMIT
  for i,v in enumerate(g.history[-8:]):f[55:58,10+i*5:14+i*5]=COMMIT if v==4 else ARROW
  if g.bad:f[1:4,18:46]=BAD
  return f
class A047(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a047",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos,self.selected,self.reservations,self.phase,self.history,self.snapshot=((0,2,4),0,(-1,-1,-1),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.selected,self.reservations,self.phase,self.history,self.snapshot=advance((self.pos,self.selected,self.reservations,self.phase,self.history,self.snapshot),a)
  elif a==6:
   if (self.pos,self.selected,self.reservations,self.phase,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
