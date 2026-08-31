"""a132 Orbit Representative -- select exactly one cell from every generated orbit."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BOARD,CELL,SELECTED,GEN_A,GEN_B,CURSOR,ORBIT,MISSING,DUPLICATE=14,8,7,12,10,13,11,4,6,9
BAD=15
LEVELS=[
 {"name":"Select Cell","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Add Generator","seq":(3,1)},{"name":"Cover Orbits","seq":(1,2,3,4,2)},
 {"name":"One Per Orbit","seq":(1,3,2,1,4,3,2)},{"name":"Orbit Representative","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def orbit_key(i,generator):
 x,y=i%4,i//4;vals={(x,y),(3-x,3-y)}
 if generator:vals|={(y,3-x),(3-y,x),(3-x,y),(x,3-y)}
 return min(a+4*b for a,b in vals)
def advance(s,a):
 selected,cursor,generator,covered,missing,duplicates,history,snapshot=s
 if a==1:selected^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%16;history=(history+(2,))[-8:]
 elif a==3:generator=1-generator;history=(history+(3,))[-8:]
 elif a==4:
  keys=[orbit_key(i,generator) for i in range(16)];all_keys=set(keys);counts={k:sum(int((selected>>i)&1) for i,x in enumerate(keys) if x==k) for k in all_keys};covered=sum(int(v>0) for v in counts.values());missing=sum(int(v==0) for v in counts.values());duplicates=sum(max(0,v-1) for v in counts.values());history=(history+(4,))[-8:]
 elif a==5:snapshot=(selected,cursor,generator,covered,missing,duplicates,history)
 return selected,cursor,generator,covered,missing,duplicates,history,snapshot
for q in LEVELS:
 s=(0b0000000100000001,0,0,2,6,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BOARD
  for i in range(16):
   x=9+(i%4)*12;y=10+(i//4)*11;f[y:y+9,x:x+9]=SELECTED if (g.selected>>i)&1 else CELL
   if i==g.cursor:f[y-3:y,x:x+9]=CURSOR
  f[54:58,8:28]=GEN_B if g.generator else GEN_A;f[54:58,31:31+g.covered*4]=ORBIT;f[7:10,8:8+g.missing*5]=MISSING;f[7:10,43:43+g.duplicates*3]=DUPLICATE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A132(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a132",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.selected,self.cursor,self.generator,self.covered,self.missing,self.duplicates,self.history,self.snapshot=(0b0000000100000001,0,0,2,6,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.selected,self.cursor,self.generator,self.covered,self.missing,self.duplicates,self.history,self.snapshot=advance((self.selected,self.cursor,self.generator,self.covered,self.missing,self.duplicates,self.history,self.snapshot),a)
  elif a==6:
   if (self.selected,self.cursor,self.generator,self.covered,self.missing,self.duplicates,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
