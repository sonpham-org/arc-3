"""a180 Unsat Core -- highlight a smallest already-contradictory constraint subset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAYOUT,CONSTRAINT_A,CONSTRAINT_B,SELECTED,CURSOR,CONFLICT,CORE,FADED,EXCESS=1,8,12,14,13,11,6,4,7,9
BAD=15
CONFLICTS=((0,2,5),(1,3,6),(2,4,7))
LEVELS=[
 {"name":"Select Constraint","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Fade Others","seq":(3,1)},{"name":"Find Conflict","seq":(1,2,3,4,2)},
 {"name":"Minimize Core","seq":(1,3,2,1,4,3,2)},{"name":"Unsat Core","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 selected,cursor,fade,conflict,core_size,excess,history,snapshot=s
 if a==1:selected^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:fade=1-fade;history=(history+(3,))[-8:]
 elif a==4:
  conflict=int(any(all((selected>>i)&1 for i in c) for c in CONFLICTS));core_size=selected.bit_count();excess=max(0,core_size-3);history=(history+(4,))[-8:]
 elif a==5:snapshot=(selected,cursor,fade,conflict,core_size,excess,history)
 return selected,cursor,fade,conflict,core_size,excess,history,snapshot
for q in LEVELS:
 s=(0b00100101,0,0,1,3,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAYOUT
  for i in range(8):
   x=9+(i%4)*13;y=13+(i//4)*22;col=SELECTED if (g.selected>>i)&1 else FADED if g.fade else CONSTRAINT_A if i%2==0 else CONSTRAINT_B;f[y:y+16,x:x+11]=col
   if i==g.cursor:f[y-3:y,x:x+11]=CURSOR
  f[54:58,8:28]=CORE if g.conflict else CONFLICT;f[54:58,31:31+g.core_size*4]=SELECTED;f[7:10,8:8+g.excess*8]=EXCESS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A180(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a180",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.selected,self.cursor,self.fade,self.conflict,self.core_size,self.excess,self.history,self.snapshot=(0b00100101,0,0,1,3,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.selected,self.cursor,self.fade,self.conflict,self.core_size,self.excess,self.history,self.snapshot=advance((self.selected,self.cursor,self.fade,self.conflict,self.core_size,self.excess,self.history,self.snapshot),a)
  elif a==6:
   if (self.selected,self.cursor,self.fade,self.conflict,self.core_size,self.excess,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
