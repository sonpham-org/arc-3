"""a140 Conjugate Corridor -- transport a local move through a rotated basis."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CORRIDOR,GRID,ACTOR,ENTRY,LOCAL,EXIT,TARGET,MATCH,MISS=6,8,7,12,10,14,13,4,11,9
BAD=15
DIRS=((1,0),(0,1),(-1,0),(0,-1))
LEVELS=[
 {"name":"Enter Basis","seq":(1,)},{"name":"Apply Local Move","seq":(2,)},
 {"name":"Exit Basis","seq":(3,1)},{"name":"Conjugate Control","seq":(1,2,3,4,2)},
 {"name":"Match Global Move","seq":(1,3,2,1,4,3,2)},{"name":"Conjugate Corridor","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 x,y,basis,local_moves,global_dir,matches,history,snapshot=s
 if a==1:basis=(basis+1)%4;history=(history+(1,))[-8:]
 elif a==2:
  dx,dy=DIRS[basis];x=(x+dx)%5;y=(y+dy)%5;local_moves=(local_moves+1)%6;history=(history+(2,))[-8:]
 elif a==3:global_dir=(global_dir-basis)%4;basis=0;history=(history+(3,))[-8:]
 elif a==4:matches=int((x,y)==((2+DIRS[global_dir][0])%5,(2+DIRS[global_dir][1])%5));history=(history+(4,))[-8:]
 elif a==5:snapshot=(x,y,basis,local_moves,global_dir,matches,history)
 return x,y,basis,local_moves,global_dir,matches,history,snapshot
for q in LEVELS:
 s=(2,2,0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CORRIDOR
  for i in range(6):f[9+i*9:11+i*9,9:55]=GRID;f[9:55,9+i*9:11+i*9]=GRID
  px=10+g.x*9;py=10+g.y*9;f[py:py+8,px:px+8]=ACTOR;f[9:13,8:20]=ENTRY;f[9:13,23:35]=LOCAL;f[9:13,38:50]=EXIT
  tx=10+(2+DIRS[g.global_dir][0])*9;ty=10+(2+DIRS[g.global_dir][1])*9;f[ty+2:ty+6,tx+2:tx+6]=TARGET
  f[54:58,8:48]=MATCH if g.matches else MISS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A140(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a140",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.x,self.y,self.basis,self.local_moves,self.global_dir,self.matches,self.history,self.snapshot=(2,2,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.x,self.y,self.basis,self.local_moves,self.global_dir,self.matches,self.history,self.snapshot=advance((self.x,self.y,self.basis,self.local_moves,self.global_dir,self.matches,self.history,self.snapshot),a)
  elif a==6:
   if (self.x,self.y,self.basis,self.local_moves,self.global_dir,self.matches,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
