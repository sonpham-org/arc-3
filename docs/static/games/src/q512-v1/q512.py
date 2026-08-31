"""q512 Lockwater Frame -- track barge identity through exchanged appearance and position."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,WATER,BARGE,FRAME,TRAIL,SWAP,ASSIGN,BAD=9,10,12,14,5,11,6,7,15
LEVELS=[{"name":"First Exchange","plan":(1,4,5)},{"name":"Rotated Barge","plan":(2,3,4,5)},{"name":"Crossed Motion","plan":(1,3,2,4,5)},{"name":"Translated Lock","plan":(3,1,4,2,5)},{"name":"Second Exchange","plan":(1,4,3,2,4,5)},{"name":"Lockwater Frame","plan":(3,1,2,4,3,1,4,2,5)}]
def advance(s,a):
 entities,rotation,offset,history,swapped,assignment=s;entities=[list(e) for e in entities];history=list(history)
 if a in (1,2):
  i=a-1;entities[i][2]=(entities[i][2]+rotation+offset+i+1)%12;history.append((entities[i][0],entities[i][2]))
 elif a==3:rotation=(rotation+1)%4;history.append((3,rotation))
 elif a==4:
  offset=(offset+1)%4;entities[0][1],entities[1][1]=entities[1][1],entities[0][1];entities[0][2],entities[1][2]=entities[1][2],entities[0][2];swapped=True;history.append((4,tuple(tuple(e) for e in entities)))
 elif a==5:
  if not swapped:return None
  assignment=tuple((e[0],e[2],e[1]) for e in sorted(entities));history.append((5,assignment))
 return tuple(tuple(e) for e in entities),rotation,offset,tuple(history),swapped,assignment
def target(x):
 s=(((1,0,2),(2,3,9)),0,0,(),False,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CANAL;f[8:33,7:29]=WATER;f[8:33,35:57]=FRAME
  for i,(ident,look,pos) in enumerate(g.entities):x=10+i*28;f[11+(pos%8)*2:17+(pos%8)*2,x:x+14]=BARGE-look;f[29:31,x:x+2+ident]=TRAIL
  f[38:41,8:11+g.rotation*11]=FRAME;f[45:48,8:11+g.offset*11]=SWAP;f[53:56,8:24]=TRAIL;f[56:59,40:56]=ASSIGN if g.assignment else WATER
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q512(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q512",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.entities=((1,0,2),(2,3,9));self.rotation=self.offset=0;self.history=();self.swapped=False;self.assignment=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.entities,self.rotation,self.offset,self.history,self.swapped,self.assignment),a)
   if s is None:self.bad=True;self.lose()
   else:self.entities,self.rotation,self.offset,self.history,self.swapped,self.assignment=s
  elif a==6:
   if (self.entities,self.rotation,self.offset,self.history,self.swapped,self.assignment)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
