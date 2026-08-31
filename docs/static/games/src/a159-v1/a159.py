"""a159 Negative Space Class -- pair pieces by equivalent enclosed holes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,STUDIO,SOLID_A,SOLID_B,HOLE_A,HOLE_B,PAIR,CURSOR,ROTATE,MATCH=11,8,12,14,4,10,9,13,7,6
BAD=15
HOLES=(0,1,1,2,0,2)
LEVELS=[
 {"name":"Choose Pair","seq":(1,)},{"name":"Select Piece","seq":(2,)},
 {"name":"Rotate Piece","seq":(3,1)},{"name":"Compare Holes","seq":(1,2,3,4,2)},
 {"name":"Ignore Foreground","seq":(1,3,2,1,4,3,2)},{"name":"Negative Space Class","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 partners,rotations,cursor,matches,errors,history,snapshot=s;p=list(partners);r=list(rotations)
 if a==1:p[cursor]=(p[cursor]+1)%6;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:r[cursor]=(r[cursor]+1)%4;history=(history+(3,))[-8:]
 elif a==4:matches=sum(int(HOLES[i]==HOLES[p[i]]) for i in range(6));errors=6-matches;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),tuple(r),cursor,matches,errors,history)
 return tuple(p),tuple(r),cursor,matches,errors,history,snapshot
for q in LEVELS:
 s=((4,2,1,5,0,3),(0,1,2,3,0,1),0,6,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STUDIO
  for i,(partner,rot) in enumerate(zip(g.partners,g.rotations)):
   x=9+(i%3)*17;y=13+(i//3)*22;f[y:y+16,x:x+14]=SOLID_A if i%2==0 else SOLID_B;hole=HOLES[i];f[y+4:y+12,x+4:x+10]=HOLE_A if hole==0 else HOLE_B if hole==1 else STUDIO;f[y+2:y+5,x+2:x+5]=ROTATE
   if i==g.cursor:f[y-3:y,x:x+14]=CURSOR
  f[54:58,8:8+g.matches*7]=MATCH;f[7:10,8:8+g.errors*7]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A159(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a159",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.partners,self.rotations,self.cursor,self.matches,self.errors,self.history,self.snapshot=((4,2,1,5,0,3),(0,1,2,3,0,1),0,6,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.partners,self.rotations,self.cursor,self.matches,self.errors,self.history,self.snapshot=advance((self.partners,self.rotations,self.cursor,self.matches,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.partners,self.rotations,self.cursor,self.matches,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
